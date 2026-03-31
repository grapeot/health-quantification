import Foundation
import HealthKit
import Observation

@MainActor
@Observable
final class HealthKitService {
    var healthDataAvailableText = "unknown"
    var authorizationState = "not_requested"
    var lastUpdated = "never"
    var logEntries: [String] = []

    private let healthStore = HKHealthStore()
    private let processInfo: ProcessInfo

    init(processInfo: ProcessInfo = .processInfo) {
        self.processInfo = processInfo
    }

    var logText: String {
        if logEntries.isEmpty {
            return "No events yet. Tap Run Doctor, Request Sleep Access, or Export Sleep (30 days)."
        }
        return logEntries.joined(separator: "\n\n")
    }

    func runDoctor() {
        let available = isUITestMockHealthDataAvailable ? true : HKHealthStore.isHealthDataAvailable()
        healthDataAvailableText = available ? "true" : "false"
        lastUpdated = Self.isoTimestamp(Date())
        appendLog(
            title: "doctor",
            payload: [
                "platform": "iOS",
                "healthDataAvailable": healthDataAvailableText,
                "timestamp": lastUpdated,
            ]
        )
    }

    func requestSleepAccess() {
        runDoctor()

        guard !isUITestMockHealthDataAvailable else {
            authorizationState = "granted"
            lastUpdated = Self.isoTimestamp(Date())
            appendLog(
                title: "requestSleepAccess",
                payload: [
                    "result": authorizationState,
                    "timestamp": lastUpdated,
                ]
            )
            return
        }

        guard HKHealthStore.isHealthDataAvailable() else {
            authorizationState = "health_data_unavailable"
            appendLog(title: "requestSleepAccess", payload: ["result": authorizationState])
            return
        }

        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else {
            authorizationState = "sleep_type_unavailable"
            appendLog(title: "requestSleepAccess", payload: ["result": authorizationState])
            return
        }

        healthStore.requestAuthorization(toShare: [], read: [sleepType]) { success, error in
            Task { @MainActor in
                self.lastUpdated = Self.isoTimestamp(Date())
                if let error {
                    self.authorizationState = "error"
                    self.appendLog(
                        title: "requestSleepAccess",
                        payload: [
                            "error": error.localizedDescription,
                            "timestamp": self.lastUpdated,
                        ]
                    )
                    return
                }

                self.authorizationState = success ? "granted" : "denied"
                self.appendLog(
                    title: "requestSleepAccess",
                    payload: [
                        "result": self.authorizationState,
                        "timestamp": self.lastUpdated,
                    ]
                )
            }
        }
    }

    func fetchSleepSamples(days: Int) async throws -> [SleepSampleRecord] {
        runDoctor()

        guard HKHealthStore.isHealthDataAvailable() || isUITestMockHealthDataAvailable else {
            authorizationState = "health_data_unavailable"
            appendLog(title: "fetchSleepSamples", payload: ["result": authorizationState])
            return []
        }

        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else {
            authorizationState = "sleep_type_unavailable"
            appendLog(title: "fetchSleepSamples", payload: ["result": authorizationState])
            return []
        }

        if !isUITestMockHealthDataAvailable {
            try await requestReadAuthorization(sleepType: sleepType)
        } else {
            authorizationState = "granted"
        }

        let now = Date()
        let startDate = Calendar.current.date(byAdding: .day, value: -days, to: now) ?? now
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: now, options: [])
        let sortDescriptors = [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)]

        let records: [SleepSampleRecord] = try await withCheckedThrowingContinuation { continuation in
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
                let records = categorySamples.map { sample in
                    SleepSampleRecord(
                        sourceID: sample.uuid.uuidString,
                        startAt: Self.isoTimestamp(sample.startDate),
                        endAt: Self.isoTimestamp(sample.endDate),
                        stage: Self.stageName(for: sample.value),
                        stageValue: Self.normalizedStageValue(for: sample.value),
                        sourceBundleID: sample.sourceRevision.source.bundleIdentifier,
                        sourceName: sample.sourceRevision.source.name,
                        metadata: [:]
                    )
                }
                continuation.resume(returning: records)
            }
            self.healthStore.execute(query)
        }

        authorizationState = "granted"
        lastUpdated = Self.isoTimestamp(now)
        appendLog(
            title: "fetchSleepSamples",
            payload: [
                "days": String(days),
                "samples": String(records.count),
                "timestamp": lastUpdated,
            ]
        )
        return records
    }

    nonisolated static func stageName(for rawValue: Int) -> String {
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

    nonisolated static func normalizedStageValue(for rawValue: Int) -> Int {
        guard let stage = HKCategoryValueSleepAnalysis(rawValue: rawValue) else {
            return rawValue
        }

        switch stage {
        case .inBed:
            return 0
        case .awake:
            return 1
        case .asleepCore:
            return 2
        case .asleepDeep:
            return 3
        case .asleepREM:
            return 4
        case .asleepUnspecified:
            return 5
        @unknown default:
            return rawValue
        }
    }

    nonisolated static func isoTimestamp(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        return formatter.string(from: date)
    }

    private var isUITestMockHealthDataAvailable: Bool {
        processInfo.arguments.contains("UITEST_HEALTH_DATA_AVAILABLE_TRUE")
    }

    private func requestReadAuthorization(sleepType: HKCategoryType) async throws {
        let readTypes: Set<HKObjectType> = [sleepType]
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            healthStore.requestAuthorization(toShare: [], read: readTypes) { success, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                if success {
                    continuation.resume(returning: ())
                    return
                }
                continuation.resume(throwing: HealthKitServiceError.authorizationDenied)
            }
        }
    }

    private func appendLog(title: String, payload: [String: String]) {
        let data = try? JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys])
        let text = String(data: data ?? Data("{}".utf8), encoding: .utf8) ?? "{}"
        let block = "[\(title)]\n\(text)"
        logEntries.append(block)
        print(block)
    }
}

enum HealthKitServiceError: LocalizedError {
    case authorizationDenied

    var errorDescription: String? {
        switch self {
        case .authorizationDenied:
            return "HealthKit authorization was not granted."
        }
    }
}
