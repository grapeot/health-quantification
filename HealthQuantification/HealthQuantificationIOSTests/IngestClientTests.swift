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

    func testEcgServerErrorOmitsResponseBody() async throws {
        let marker = "SYNTHETIC-WAVE-0.009876"
        SyntheticIngestURLProtocol.statusCode = 422
        SyntheticIngestURLProtocol.body = Data("{\"detail\":\"\(marker)\"}".utf8)
        let client = IngestClient(session: Self.stubSession())
        let sample = ECGRecord(
            sourceID: "ecg-synthetic",
            startAt: "2026-03-31T02:00:00Z",
            endAt: "2026-03-31T02:00:30Z",
            algorithmClassification: "sinus_rhythm",
            algorithmClassificationValue: 1,
            symptomsStatus: "none",
            symptomsStatusValue: 1,
            averageHeartRateBPM: 60,
            samplingFrequencyHz: 512,
            numberOfVoltageMeasurements: 1,
            voltageCount: 1,
            voltageUnit: "V",
            lead: "apple_watch_similar_to_lead_i",
            voltageStatus: "partial",
            voltageErrorCode: "voltage_count_mismatch",
            algorithmVersion: 2,
            sourceBundleID: "com.apple.health",
            sourceName: "Health",
            symptoms: [],
            symptomsReadStatus: "not_applicable",
            metadata: [:],
            voltage: [ECGVoltagePoint(timeOffsetSeconds: 0, voltageVolts: 0.1)]
        )

        do {
            _ = try await client.ingestEcg(
                serverURL: try XCTUnwrap(URL(string: "http://127.0.0.1:9")),
                samples: [sample]
            )
            XCTFail("expected server error")
        } catch let error as IngestClientError {
            let text = error.localizedDescription
            XCTAssertEqual(text, "Server error 422.")
            XCTAssertFalse(text.contains(marker))
            XCTAssertFalse(text.contains("0.009876"))
        }
    }

    func testNonEcgServerErrorStillIncludesStatusMessage() async throws {
        SyntheticIngestURLProtocol.statusCode = 422
        SyntheticIngestURLProtocol.body = Data("{\"detail\":\"missing samples\"}".utf8)
        let client = IngestClient(session: Self.stubSession())
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

        do {
            _ = try await client.ingestSleep(
                serverURL: try XCTUnwrap(URL(string: "http://127.0.0.1:9")),
                samples: [sample]
            )
            XCTFail("expected server error")
        } catch let error as IngestClientError {
            XCTAssertEqual(error.localizedDescription, "Server error 422: {\"detail\":\"missing samples\"}")
        }
    }

    private static func stubSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [SyntheticIngestURLProtocol.self]
        return URLSession(configuration: configuration)
    }

    @MainActor
    func testVitalsBatchesPreserveEverySampleAndAggregateResponses() async throws {
        VitalsBatchURLProtocol.receivedIDs = []
        VitalsBatchURLProtocol.batchSizes = []
        VitalsBatchURLProtocol.failRequest = nil
        let samples = (0..<4_003).map { index in
            VitalsSampleRecord(sourceID: "synthetic-\(index)", recordedAt: "2026-03-31T06:30:00Z",
                               metricType: "heart_rate", value: 60, unit: "count/min",
                               sourceBundleID: "test.synthetic", sourceName: "Synthetic", metadata: [:])
        }
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [VitalsBatchURLProtocol.self]
        var progress: [Int] = []
        let client = IngestClient(session: URLSession(configuration: configuration), onVitalsProgress: { completed, _ in
            progress.append(completed)
        })
        let response = try await client.ingestVitals(serverURL: URL(string: "http://127.0.0.1:9")!, samples: samples)
        XCTAssertEqual(VitalsBatchURLProtocol.batchSizes, [2_000, 2_000, 3])
        XCTAssertEqual(VitalsBatchURLProtocol.receivedIDs, samples.map(\.sourceID))
        XCTAssertEqual(response.upserted, samples.count)
        XCTAssertEqual(response.totalSamples, samples.count)
        XCTAssertEqual(progress, [0, 2000, 4000, 4003])
    }

    @MainActor
    func testVitalsBatchFailureDoesNotReportSuccessOrSendLaterBatches() async throws {
        VitalsBatchURLProtocol.receivedIDs = []
        VitalsBatchURLProtocol.batchSizes = []
        VitalsBatchURLProtocol.failRequest = 2
        defer { VitalsBatchURLProtocol.failRequest = nil }
        let sample = VitalsSampleRecord(sourceID: "synthetic", recordedAt: "2026-03-31T06:30:00Z",
                                       metricType: "heart_rate", value: 60, unit: "count/min",
                                       sourceBundleID: "test.synthetic", sourceName: "Synthetic", metadata: [:])
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [VitalsBatchURLProtocol.self]
        var progress: [Int] = []
        let client = IngestClient(session: URLSession(configuration: configuration), onVitalsProgress: { completed, _ in
            progress.append(completed)
        })
        do {
            _ = try await client.ingestVitals(serverURL: URL(string: "http://127.0.0.1:9")!,
                                             samples: Array(repeating: sample, count: 4_003))
            XCTFail("A failed batch must fail the category")
        } catch {
            XCTAssertEqual(VitalsBatchURLProtocol.batchSizes, [2_000, 2_000])
            let failure = try XCTUnwrap(error as? VitalsBatchUploadError)
            XCTAssertEqual(failure.acknowledged, 2000)
            XCTAssertEqual(failure.upserted, 2000)
            XCTAssertEqual(failure.failedBatch, 2)
            XCTAssertEqual(progress, [0, 2000])
        }
    }
}

private final class VitalsBatchURLProtocol: URLProtocol {
    static var receivedIDs: [String] = []
    static var batchSizes: [Int] = []
    static var failRequest: Int?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        do {
            var data = request.httpBody ?? Data()
            if let stream = request.httpBodyStream {
                stream.open()
                defer { stream.close() }
                var buffer = [UInt8](repeating: 0, count: 4096)
                while stream.hasBytesAvailable {
                    let count = stream.read(&buffer, maxLength: buffer.count)
                    if count <= 0 { break }
                    data.append(buffer, count: count)
                }
            }
            let envelope = try JSONSerialization.jsonObject(with: data) as! [String: Any]
            let samples = envelope["samples"] as! [[String: Any]]
            Self.batchSizes.append(samples.count)
            if Self.batchSizes.count == Self.failRequest {
                client?.urlProtocol(self, didFailWithError: URLError(.timedOut))
                return
            }
            Self.receivedIDs.append(contentsOf: samples.map { $0["source_id"] as! String })
            let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: try JSONSerialization.data(withJSONObject: [
                "status": "accepted", "upserted": samples.count, "total_samples": Self.receivedIDs.count]))
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }
    override func stopLoading() {}
}

private final class SyntheticIngestURLProtocol: URLProtocol {
    static var statusCode = 422
    static var body = Data()

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        let response = HTTPURLResponse(
            url: request.url ?? URL(string: "http://127.0.0.1:9")!,
            statusCode: Self.statusCode,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        )
        if let response {
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        }
        client?.urlProtocol(self, didLoad: Self.body)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
