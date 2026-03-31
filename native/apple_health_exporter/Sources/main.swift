import Foundation
import HealthKit

enum ExporterError: Error {
    case invalidArguments(String)
    case healthDataUnavailable
    case unsupportedMetric(String)
}

struct DoctorPayload: Encodable {
    let executablePath: String
    let currentDirectory: String
    let platform: String
    let healthDataAvailable: Bool
    let timestamp: String
}

struct ExportEnvelope: Encodable {
    let source: String
    let metric: String
    let exportedAt: String
    let schemaVersion: String
    let queryDays: Int
    let samples: [SleepSamplePayload]
}

struct SleepSamplePayload: Encodable {
    let startAt: String
    let endAt: String
    let value: Int
    let stage: String
    let sourceBundleIdentifier: String
    let sourceName: String
}

enum Command {
    case doctor
    case exportSleep(days: Int, output: String)
}

@main
struct AppleHealthExporter {
    static func main() async {
        do {
            let command = try parseCommand(arguments: CommandLine.arguments)
            switch command {
            case .doctor:
                try runDoctor()
            case let .exportSleep(days, output):
                try await runSleepExport(days: days, output: output)
            }
        } catch {
            let payload = [
                "status": "error",
                "message": String(describing: error),
            ]
            try? emitJSON(payload)
            Foundation.exit(1)
        }
    }

    static func parseCommand(arguments: [String]) throws -> Command {
        guard arguments.count >= 2 else {
            throw ExporterError.invalidArguments("Expected a command: doctor | export sleep --days N --output <path>")
        }

        switch arguments[1] {
        case "doctor":
            return .doctor
        case "export":
            return try parseExport(arguments: Array(arguments.dropFirst(2)))
        default:
            throw ExporterError.invalidArguments("Unsupported command: \(arguments[1])")
        }
    }

    static func parseExport(arguments: [String]) throws -> Command {
        guard let metric = arguments.first else {
            throw ExporterError.invalidArguments("Expected export metric: sleep")
        }
        guard metric == "sleep" else {
            throw ExporterError.unsupportedMetric(metric)
        }

        var days = 7
        var output: String?
        var index = 1
        while index < arguments.count {
            let current = arguments[index]
            if current == "--days" {
                let nextIndex = index + 1
                guard nextIndex < arguments.count, let parsed = Int(arguments[nextIndex]) else {
                    throw ExporterError.invalidArguments("Invalid value for --days")
                }
                days = parsed
                index += 2
                continue
            }
            if current == "--output" {
                let nextIndex = index + 1
                guard nextIndex < arguments.count else {
                    throw ExporterError.invalidArguments("Missing value for --output")
                }
                output = arguments[nextIndex]
                index += 2
                continue
            }
            throw ExporterError.invalidArguments("Unknown export flag: \(current)")
        }

        guard let output else {
            throw ExporterError.invalidArguments("Missing required flag: --output")
        }

        return .exportSleep(days: days, output: output)
    }

    static func runDoctor() throws {
        let payload = DoctorPayload(
            executablePath: CommandLine.arguments.first ?? "unknown",
            currentDirectory: FileManager.default.currentDirectoryPath,
            platform: "macOS",
            healthDataAvailable: HKHealthStore.isHealthDataAvailable(),
            timestamp: isoTimestamp(Date())
        )
        try emitJSON(payload)
    }

    static func runSleepExport(days: Int, output: String) async throws {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw ExporterError.healthDataUnavailable
        }

        let store = HKHealthStore()
        let samples = try await requestSleepSamples(store: store, days: days)
        let payload = ExportEnvelope(
            source: "apple_health_exporter",
            metric: "sleep",
            exportedAt: isoTimestamp(Date()),
            schemaVersion: "0.1.0",
            queryDays: days,
            samples: samples
        )
        try writeJSON(payload, outputPath: output)
    }

    static func requestSleepSamples(store: HKHealthStore, days: Int) async throws -> [SleepSamplePayload] {
        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else {
            return []
        }

        try await requestReadAuthorization(store: store, sleepType: sleepType)

        let now = Date()
        let calendar = Calendar.current
        let startDate = calendar.date(byAdding: .day, value: -days, to: now) ?? now
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: now, options: [])
        let sortDescriptors = [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)]

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: sleepType,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: sortDescriptors
            ) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                let categorySamples = (samples as? [HKCategorySample]) ?? []
                let payloads = categorySamples.map { sample in
                    SleepSamplePayload(
                        startAt: isoTimestamp(sample.startDate),
                        endAt: isoTimestamp(sample.endDate),
                        value: sample.value,
                        stage: sleepStageName(rawValue: sample.value),
                        sourceBundleIdentifier: sample.sourceRevision.source.bundleIdentifier,
                        sourceName: sample.sourceRevision.source.name
                    )
                }
                continuation.resume(returning: payloads)
            }
            store.execute(query)
        }
    }

    static func requestReadAuthorization(store: HKHealthStore, sleepType: HKCategoryType) async throws {
        let readTypes: Set<HKObjectType> = [sleepType]
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            store.requestAuthorization(toShare: [], read: readTypes) { success, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                if success {
                    continuation.resume(returning: ())
                    return
                }
                continuation.resume(throwing: ExporterError.invalidArguments("HealthKit authorization was not granted"))
            }
        }
    }

    static func sleepStageName(rawValue: Int) -> String {
        guard let stage = HKCategoryValueSleepAnalysis(rawValue: rawValue) else {
            return "unknown"
        }

        switch stage {
        case .inBed:
            return "in_bed"
        case .awake:
            return "awake"
        case .asleepCore:
            return "asleep_core"
        case .asleepDeep:
            return "asleep_deep"
        case .asleepREM:
            return "asleep_rem"
        case .asleepUnspecified:
            return "asleep_unspecified"
        @unknown default:
            return "unknown"
        }
    }

    static func writeJSON<T: Encodable>(_ value: T, outputPath: String) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(value)
        let url = URL(fileURLWithPath: outputPath)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: url)
        try emitJSON([
            "status": "written",
            "output": outputPath,
        ])
    }

    static func emitJSON<T: Encodable>(_ value: T) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(value)
        if let text = String(data: data, encoding: .utf8) {
            print(text)
        }
    }

    static func isoTimestamp(_ date: Date) -> String {
        ISO8601DateFormatter().string(from: date)
    }
}
