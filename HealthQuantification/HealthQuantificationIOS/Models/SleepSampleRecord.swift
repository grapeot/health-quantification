import Foundation

struct SleepSampleRecord: Codable, Equatable {
    let sourceID: String
    let startAt: String
    let endAt: String
    let stage: String
    let stageValue: Int
    let sourceBundleID: String
    let sourceName: String
    let metadata: [String: String]

    enum CodingKeys: String, CodingKey {
        case sourceID = "source_id"
        case startAt = "start_at"
        case endAt = "end_at"
        case stage
        case stageValue = "stage_value"
        case sourceBundleID = "source_bundle_id"
        case sourceName = "source_name"
        case metadata
    }
}
