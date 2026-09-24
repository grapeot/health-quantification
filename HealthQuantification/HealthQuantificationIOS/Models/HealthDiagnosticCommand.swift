import Foundation

struct HealthDiagnosticCommand: Equatable {
    let runID: UUID
    let days: Int
}

enum HealthDiagnosticDeepLinkParser {
    static func parse(_ url: URL) -> HealthDiagnosticCommand? {
        guard url.scheme?.lowercased() == "healthquantification",
              url.host?.lowercased() == "diagnostics",
              url.path.isEmpty || url.path == "/",
              url.user == nil,
              url.password == nil,
              url.port == nil,
              url.fragment == nil,
              let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems,
              items.count == 3,
              Set(items.map(\.name)) == Set(["kind", "run_id", "days"]),
              items.first(where: { $0.name == "kind" })?.value == "physical-effort",
              let idString = items.first(where: { $0.name == "run_id" })?.value,
              idString.count == 36,
              let runID = UUID(uuidString: idString),
              let daysString = items.first(where: { $0.name == "days" })?.value,
              let days = Int(daysString),
              String(days) == daysString,
              (1...30).contains(days) else {
            return nil
        }
        return HealthDiagnosticCommand(runID: runID, days: days)
    }
}

struct HealthDiagnosticArtifact: Codable, Equatable {
    let schemaVersion: Int
    let runID: String
    let kind: String
    let status: String
    let generatedAt: String
    let days: Int
    let sampleCount: Int?
    let unit: String?
    let minimum: Double?
    let median: Double?
    let p90: Double?
    let maximum: Double?
    let errorCode: String?
}

enum HealthDiagnosticArtifactStore {
    static func save(_ artifact: HealthDiagnosticArtifact, in directory: URL? = nil) throws -> URL {
        let root = try directory ?? FileManager.default.url(
            for: .cachesDirectory, in: .userDomainMask, appropriateFor: nil, create: true
        ).appending(path: "Diagnostics", directoryHint: .isDirectory)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let url = root.appending(path: "\(artifact.runID).json")
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        try encoder.encode(artifact).write(to: url, options: .atomic)
        #if os(iOS)
        try FileManager.default.setAttributes(
            [.protectionKey: FileProtectionType.complete], ofItemAtPath: url.path
        )
        #endif

        let expiry = Date().addingTimeInterval(-24 * 60 * 60)
        for file in try FileManager.default.contentsOfDirectory(
            at: root, includingPropertiesForKeys: [.contentModificationDateKey]
        ) where file.pathExtension == "json" && file != url {
            if (try? file.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantFuture < expiry {
                try? FileManager.default.removeItem(at: file)
            }
        }
        return url
    }
}
