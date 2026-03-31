import Foundation

struct IngestEnvelope: Codable, Equatable {
    let source: String
    let exportedAt: String
    let schemaVersion: String
    let samples: [SleepSampleRecord]

    init(samples: [SleepSampleRecord], exportedAt: String = HealthKitService.isoTimestamp(Date())) {
        self.source = "apple_health_ios"
        self.exportedAt = exportedAt
        self.schemaVersion = "0.1.0"
        self.samples = samples
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
