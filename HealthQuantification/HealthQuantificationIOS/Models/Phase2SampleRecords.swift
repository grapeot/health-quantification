import Foundation

struct VitalsSampleRecord: Codable, Equatable {
    let sourceID: String
    let recordedAt: String
    let metricType: String
    let value: Double
    let unit: String
    let sourceBundleID: String
    let sourceName: String
    let metadata: [String: String]

    enum CodingKeys: String, CodingKey {
        case sourceID = "source_id"
        case recordedAt = "recorded_at"
        case metricType = "metric_type"
        case value
        case unit
        case sourceBundleID = "source_bundle_id"
        case sourceName = "source_name"
        case metadata
    }
}

struct BodySampleRecord: Codable, Equatable {
    let sourceID: String
    let recordedAt: String
    let metricType: String
    let value: Double
    let unit: String
    let sourceBundleID: String
    let sourceName: String
    let metadata: [String: String]

    enum CodingKeys: String, CodingKey {
        case sourceID = "source_id"
        case recordedAt = "recorded_at"
        case metricType = "metric_type"
        case value
        case unit
        case sourceBundleID = "source_bundle_id"
        case sourceName = "source_name"
        case metadata
    }
}

struct LifestyleSampleRecord: Codable, Equatable {
    let sourceID: String
    let recordedAt: String
    let metricType: String
    let value: Double
    let unit: String
    let sourceBundleID: String
    let sourceName: String
    let metadata: [String: String]

    enum CodingKeys: String, CodingKey {
        case sourceID = "source_id"
        case recordedAt = "recorded_at"
        case metricType = "metric_type"
        case value
        case unit
        case sourceBundleID = "source_bundle_id"
        case sourceName = "source_name"
        case metadata
    }
}

struct ActivitySampleRecord: Codable, Equatable {
    let sourceID: String
    let startAt: String
    let endAt: String
    let metricType: String
    let value: Double
    let unit: String
    let sourceBundleID: String
    let sourceName: String
    let metadata: [String: String]

    enum CodingKeys: String, CodingKey {
        case sourceID = "source_id"
        case startAt = "start_at"
        case endAt = "end_at"
        case metricType = "metric_type"
        case value
        case unit
        case sourceBundleID = "source_bundle_id"
        case sourceName = "source_name"
        case metadata
    }
}
