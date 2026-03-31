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

    @MainActor
    func testVitalsSampleRecordAndEnvelopeEncodeRFCFields() throws {
        let sample = VitalsSampleRecord(
            sourceID: "HR-123",
            recordedAt: "2026-03-31T06:30:00Z",
            metricType: "resting_heart_rate",
            value: 62.0,
            unit: "count/min",
            sourceBundleID: "com.apple.health",
            sourceName: "Health",
            metadata: [:]
        )
        let envelope = IngestEnvelope(samples: [sample], exportedAt: "2026-03-31T07:00:00Z")

        let data = try JSONEncoder().encode(envelope)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let samples = try XCTUnwrap(object["samples"] as? [[String: Any]])
        let firstSample = try XCTUnwrap(samples.first)

        XCTAssertEqual(object["source"] as? String, "apple_health_ios")
        XCTAssertEqual(object["exported_at"] as? String, "2026-03-31T07:00:00Z")
        XCTAssertEqual(object["schema_version"] as? String, "0.1.0")
        XCTAssertEqual(firstSample["source_id"] as? String, "HR-123")
        XCTAssertEqual(firstSample["recorded_at"] as? String, "2026-03-31T06:30:00Z")
        XCTAssertEqual(firstSample["metric_type"] as? String, "resting_heart_rate")
        XCTAssertEqual(firstSample["value"] as? Double, 62.0)
        XCTAssertEqual(firstSample["unit"] as? String, "count/min")
    }

    @MainActor
    func testBodyLifestyleAndActivityRecordsEncodeRFCFields() throws {
        let body = BodySampleRecord(
            sourceID: "BP-123",
            recordedAt: "2026-03-31T06:30:00Z",
            metricType: "blood_pressure_systolic",
            value: 118.0,
            unit: "mmHg",
            sourceBundleID: "com.apple.health",
            sourceName: "Health",
            metadata: [:]
        )
        let lifestyle = LifestyleSampleRecord(
            sourceID: "CAF-123",
            recordedAt: "2026-03-31T08:00:00Z",
            metricType: "dietary_caffeine",
            value: 150.0,
            unit: "mg",
            sourceBundleID: "com.apple.health",
            sourceName: "Health",
            metadata: [:]
        )
        let activity = ActivitySampleRecord(
            sourceID: "STEP-123",
            startAt: "2026-03-31T00:00:00Z",
            endAt: "2026-03-31T00:05:00Z",
            metricType: "step_count",
            value: 425.0,
            unit: "count",
            sourceBundleID: "com.apple.health",
            sourceName: "Health",
            metadata: [:]
        )

        let bodyObject = try jsonObject(for: body)
        let lifestyleObject = try jsonObject(for: lifestyle)
        let activityObject = try jsonObject(for: activity)

        XCTAssertEqual(bodyObject["metric_type"] as? String, "blood_pressure_systolic")
        XCTAssertEqual(bodyObject["value"] as? Double, 118.0)
        XCTAssertEqual(bodyObject["unit"] as? String, "mmHg")

        XCTAssertEqual(lifestyleObject["metric_type"] as? String, "dietary_caffeine")
        XCTAssertEqual(lifestyleObject["value"] as? Double, 150.0)
        XCTAssertEqual(lifestyleObject["unit"] as? String, "mg")

        XCTAssertEqual(activityObject["start_at"] as? String, "2026-03-31T00:00:00Z")
        XCTAssertEqual(activityObject["end_at"] as? String, "2026-03-31T00:05:00Z")
        XCTAssertEqual(activityObject["metric_type"] as? String, "step_count")
        XCTAssertEqual(activityObject["value"] as? Double, 425.0)
        XCTAssertEqual(activityObject["unit"] as? String, "count")
    }

    private func jsonObject<T: Encodable>(for value: T) throws -> [String: Any] {
        let data = try JSONEncoder().encode(value)
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }
}
