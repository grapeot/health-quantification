import Foundation

struct IngestEnvelope<Sample: Codable & Equatable>: Codable, Equatable {
    let source: String
    let exportedAt: String
    let schemaVersion: String
    let samples: [Sample]

    init(samples: [Sample], exportedAt: String = Self.defaultExportedAt()) {
        self.source = "apple_health_ios"
        self.exportedAt = exportedAt
        self.schemaVersion = "0.1.0"
        self.samples = samples
    }

    private static func defaultExportedAt() -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        return formatter.string(from: Date())
    }

    enum CodingKeys: String, CodingKey {
        case source
        case exportedAt = "exported_at"
        case schemaVersion = "schema_version"
        case samples
    }
}

struct IngestResponse: Codable, Equatable {
    let status: String
    let upserted: Int
    let totalSamples: Int

    enum CodingKeys: String, CodingKey {
        case status
        case upserted
        case totalSamples = "total_samples"
    }
}
