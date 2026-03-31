import Foundation
import XCTest
@testable import HealthQuantificationIOS

final class IngestClientTests: XCTestCase {
    @MainActor
    func testSleepSampleRecordEncodesProtocolFields() throws {
        let sample = SleepSampleRecord(
            sourceID: "ABC-123",
            startAt: "2026-03-30T22:30:00Z",
            endAt: "2026-03-31T06:30:00Z",
            stage: "asleep_deep",
            stageValue: 3,
            sourceBundleID: "com.apple.health",
            sourceName: "Health",
            metadata: [:]
        )

        let data = try JSONEncoder().encode(sample)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])

        XCTAssertEqual(object["source_id"] as? String, "ABC-123")
        XCTAssertEqual(object["start_at"] as? String, "2026-03-30T22:30:00Z")
        XCTAssertEqual(object["end_at"] as? String, "2026-03-31T06:30:00Z")
        XCTAssertEqual(object["stage"] as? String, "asleep_deep")
        XCTAssertEqual(object["stage_value"] as? Int, 3)
        XCTAssertEqual(object["source_bundle_id"] as? String, "com.apple.health")
        XCTAssertEqual(object["source_name"] as? String, "Health")
        XCTAssertEqual(object["metadata"] as? [String: String], [:])
    }

    @MainActor
    func testIngestEnvelopeEncodesExactProtocolShape() throws {
        let sample = SleepSampleRecord(
            sourceID: "ABC-123",
            startAt: "2026-03-30T22:30:00Z",
            endAt: "2026-03-31T06:30:00Z",
            stage: "asleep_deep",
            stageValue: 3,
            sourceBundleID: "com.apple.health",
            sourceName: "Health",
            metadata: [:]
        )
        let envelope = IngestEnvelope(samples: [sample], exportedAt: "2026-03-31T02:35:56Z")

        let data = try JSONEncoder().encode(envelope)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let samples = try XCTUnwrap(object["samples"] as? [[String: Any]])
        let firstSample = try XCTUnwrap(samples.first)

        XCTAssertEqual(object["source"] as? String, "apple_health_ios")
        XCTAssertEqual(object["exported_at"] as? String, "2026-03-31T02:35:56Z")
        XCTAssertEqual(object["schema_version"] as? String, "0.1.0")
        XCTAssertEqual(samples.count, 1)
        XCTAssertEqual(firstSample["source_id"] as? String, "ABC-123")
        XCTAssertEqual(firstSample["stage"] as? String, "asleep_deep")
        XCTAssertEqual(firstSample["stage_value"] as? Int, 3)
    }

    @MainActor
    func testIngestResponseDecodesFromProtocolJSON() throws {
        let data = Data(#"{"status":"accepted","upserted":12,"total_samples":12}"#.utf8)
        let response = try JSONDecoder().decode(IngestResponse.self, from: data)

        XCTAssertEqual(response, IngestResponse(status: "accepted", upserted: 12, totalSamples: 12))
    }
}
