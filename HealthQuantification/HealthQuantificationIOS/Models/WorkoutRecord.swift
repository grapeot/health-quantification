import Foundation

struct WorkoutRecord: Codable, Equatable {
    let source_id: String
    let workout_type: String
    let start_at: String
    let end_at: String
    let duration_seconds: Double?
    let total_energy_burned: Double?
    let total_distance_meters: Double?
    let source_bundle_id: String?
    let source_name: String?
    let metadata: [String: String]
}
