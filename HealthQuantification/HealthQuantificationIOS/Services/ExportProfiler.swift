import Foundation

struct ExportProfileEvent: Codable, Equatable {
    let phase: String
    let durationMs: Double
    let count: Int?
    let bytes: Int?
    enum CodingKeys: String, CodingKey {
        case phase, count, bytes
        case durationMs = "duration_ms"
    }
}

struct ExportProfileArtifact: Codable {
    let schemaVersion: Int
    let runID: String
    let status: String
    let totalMs: Double
    let events: [ExportProfileEvent]
    let failedCategories: [String]
    let buildConfiguration: String
    enum CodingKeys: String, CodingKey {
        case status, events
        case schemaVersion = "schema_version"
        case runID = "run_id"
        case totalMs = "total_ms"
        case failedCategories = "failed_categories"
        case buildConfiguration = "build_configuration"
    }
}

/// Opt-in aggregate instrumentation. Never captures sample values, URLs or error text.
final class ExportProfiler: @unchecked Sendable {
    @TaskLocal static var current: ExportProfiler?
    private let lock = NSLock()
    private var events: [ExportProfileEvent] = []
    private let started = now()
    private var lastSaved: UInt64 = 0
    private var observerNs: UInt64 = 0
    private var finished = false
    let runID: UUID
    private let directory: URL

    init(runID: UUID, directory: URL? = nil) {
        self.runID = runID
        self.directory = directory ?? FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appending(path: "ExportProfiles", directoryHint: .isDirectory)
    }

    static func now() -> UInt64 { DispatchTime.now().uptimeNanoseconds }

    func record(_ phase: String, since start: UInt64, count: Int? = nil, bytes: Int? = nil) {
        add(phase, milliseconds: Double(Self.now() - start) / 1_000_000, count: count, bytes: bytes)
    }

    func add(_ phase: String, milliseconds: Double, count: Int? = nil, bytes: Int? = nil) {
        let observerStart = Self.now()
        lock.lock()
        defer {
            observerNs += Self.now() - observerStart
            lock.unlock()
        }
        guard !finished else { return }
        events.append(.init(phase: phase, durationMs: milliseconds, count: count, bytes: bytes))
        // Progress snapshots are throttled; individual hot-loop samples are never logged.
        if Self.now() - lastSaved >= 1_000_000_000 {
            try? save(status: "running", failedCategories: [])
            lastSaved = Self.now()
        }
    }

    func finish(_ result: HealthExportResult) throws {
        lock.lock()
        defer { lock.unlock() }
        events.append(.init(phase: "profiling.progress_overhead", durationMs: Double(observerNs) / 1_000_000, count: nil, bytes: nil))
        try save(status: result.status.rawValue, failedCategories: result.failedCategories.map(\.rawValue))
        finished = true
        let expiry = Date().addingTimeInterval(-86400)
        for file in try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: [.contentModificationDateKey])
        where file.pathExtension == "json" && file.lastPathComponent != "\(runID.uuidString).json" {
            if (try? file.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantFuture < expiry {
                try? FileManager.default.removeItem(at: file)
            }
        }
    }

    private func save(status: String, failedCategories: [String]) throws {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        #if DEBUG
        let configuration = "Debug"
        #else
        let configuration = "Release"
        #endif
        let artifact = ExportProfileArtifact(
            schemaVersion: 1, runID: runID.uuidString, status: status,
            totalMs: Double(Self.now() - started) / 1_000_000,
            events: events, failedCategories: failedCategories, buildConfiguration: configuration
        )
        let encoder = JSONEncoder()
        let destination = directory.appending(path: "\(runID.uuidString).json")
        try encoder.encode(artifact).write(to: destination, options: .atomic)
        #if os(iOS)
        try FileManager.default.setAttributes([.protectionKey: FileProtectionType.complete], ofItemAtPath: destination.path)
        #endif
    }

    @MainActor
    static func measure<T>(_ phase: String, operation: () async throws -> T) async rethrows -> T {
        let start = now()
        defer { current?.record(phase, since: start) }
        return try await operation()
    }
}

final class ExportNetworkMetrics: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    let profiler: ExportProfiler
    let category: String

    init(profiler: ExportProfiler, category: String) {
        self.profiler = profiler
        self.category = category
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didFinishCollecting metrics: URLSessionTaskMetrics) {
        for metric in metrics.transactionMetrics {
            for (phase, start, end) in [
                ("connect", metric.connectStartDate, metric.connectEndDate),
                ("send", metric.requestStartDate, metric.requestEndDate),
                ("wait", metric.requestEndDate, metric.responseStartDate),
                ("receive", metric.responseStartDate, metric.responseEndDate),
            ] {
                if let start, let end {
                    profiler.add("\(category).network.\(phase)", milliseconds: max(0, end.timeIntervalSince(start) * 1000))
                }
            }
        }
    }
}
