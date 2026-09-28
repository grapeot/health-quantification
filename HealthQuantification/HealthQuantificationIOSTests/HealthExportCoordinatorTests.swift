import Foundation
import XCTest
@testable import HealthQuantificationIOS

@MainActor
final class HealthExportCoordinatorTests: XCTestCase {
    func testExportsAllCategoriesAndAggregatesCounts() async throws {
        let dataSource = FakeHealthExportDataSource()
        let ingest = FakeHealthExportIngestClient()

        let result = await HealthExportCoordinator(dataSource: dataSource, ingestClient: ingest)
            .exportAll(serverURL: try XCTUnwrap(URL(string: "http://localhost:7996")))

        XCTAssertEqual(result.status, .success)
        XCTAssertEqual(result.categoryResults.map(\.category), HealthExportCategory.allCases)
        XCTAssertEqual(ingest.categories, [.sleep, .vitals, .activity, .workouts])
    }

    func testContinuesAfterCategoryFailureAndReturnsPartial() async throws {
        let dataSource = FakeHealthExportDataSource(failingCategories: [.vitals])
        let ingest = FakeHealthExportIngestClient()

        let result = await HealthExportCoordinator(dataSource: dataSource, ingestClient: ingest)
            .exportAll(serverURL: try XCTUnwrap(URL(string: "http://localhost:7996")))

        XCTAssertEqual(result.status, .partial)
        XCTAssertEqual(result.failedCategories, [.vitals])
        XCTAssertEqual(result.categoryResults.count, HealthExportCategory.allCases.count)
        XCTAssertTrue(ingest.categories.contains(.workouts))
    }

    func testEmptyEcgDoesNotClaimNormalAndDoesNotDropOtherCategories() async throws {
        let dataSource = FakeHealthExportDataSource()
        let ingest = FakeHealthExportIngestClient()

        let result = await HealthExportCoordinator(dataSource: dataSource, ingestClient: ingest)
            .exportAll(serverURL: try XCTUnwrap(URL(string: "http://localhost:7996")))

        let ecg = try XCTUnwrap(result.categoryResults.first { $0.category == .ecg })
        XCTAssertNil(ecg.errorDescription)
        XCTAssertEqual(ecg.sent, 0)
        XCTAssertTrue(ecg.line.contains("does not prove absence"))
        XCTAssertFalse(ingest.categories.contains(.ecg))
        XCTAssertTrue(ingest.categories.contains(.workouts))
        XCTAssertEqual(result.status, .success)
    }

    func testOneEcgIngestFailureKeepsOtherHealthCategoriesAndSiblingEcg() async throws {
        let dataSource = FakeHealthExportDataSource(
            ecgSamples: [syntheticECG(sourceID: "ecg-fail"), syntheticECG(sourceID: "ecg-ok")]
        )
        let ingest = FakeHealthExportIngestClient()
        ingest.failingSourceIDs = ["ecg-fail"]

        let result = await HealthExportCoordinator(dataSource: dataSource, ingestClient: ingest)
            .exportAll(serverURL: try XCTUnwrap(URL(string: "http://localhost:7996")))

        XCTAssertEqual(result.status, .partial)
        XCTAssertEqual(result.failedCategories, [.ecg])
        XCTAssertTrue(ingest.categories.contains(.workouts))
        XCTAssertEqual(ingest.categories.filter { $0 == .ecg }.count, 1)
        let ecg = try XCTUnwrap(result.categoryResults.first { $0.category == .ecg })
        XCTAssertEqual(ecg.sent, 1)
        XCTAssertEqual(ecg.upserted, 1)
    }
}

private func syntheticECG(sourceID: String) -> ECGRecord {
    ECGRecord(
        sourceID: sourceID,
        startAt: "2026-03-31T02:00:00Z",
        endAt: "2026-03-31T02:00:30Z",
        algorithmClassification: "sinus_rhythm",
        algorithmClassificationValue: 1,
        symptomsStatus: "none",
        symptomsStatusValue: 1,
        averageHeartRateBPM: 60,
        samplingFrequencyHz: 512,
        numberOfVoltageMeasurements: 2,
        voltageCount: 2,
        voltageUnit: "V",
        lead: "apple_watch_similar_to_lead_i",
        voltageStatus: "complete",
        voltageErrorCode: nil,
        algorithmVersion: 2,
        sourceBundleID: "com.apple.health",
        sourceName: "Health",
        symptoms: [],
        symptomsReadStatus: "not_applicable",
        metadata: [:],
        voltage: [
            ECGVoltagePoint(timeOffsetSeconds: 0, voltageVolts: 0.0001),
            ECGVoltagePoint(timeOffsetSeconds: 0.001953125, voltageVolts: -0.0002),
        ]
    )
}

@MainActor
private final class FakeHealthExportDataSource: HealthExportDataSource {
    let failingCategories: Set<HealthExportCategory>
    var ecgSamples: [ECGRecord] = []

    init(failingCategories: Set<HealthExportCategory> = [], ecgSamples: [ECGRecord] = []) {
        self.failingCategories = failingCategories
        self.ecgSamples = ecgSamples
    }

    func fetchSleepSamples(days: Int) async throws -> [SleepSampleRecord] {
        try failIfNeeded(.sleep)
        return []
    }

    func fetchVitalsSamples(days: Int) async throws -> [VitalsSampleRecord] {
        try failIfNeeded(.vitals)
        return []
    }

    func fetchBodySamples(days: Int) async throws -> [BodySampleRecord] {
        try failIfNeeded(.body)
        return []
    }

    func fetchLifestyleSamples(days: Int) async throws -> [LifestyleSampleRecord] {
        try failIfNeeded(.lifestyle)
        return []
    }

    func fetchActivitySamples(days: Int) async throws -> [ActivitySampleRecord] {
        try failIfNeeded(.activity)
        return []
    }

    func fetchWorkoutSamples(days: Int) async throws -> [WorkoutRecord] {
        try failIfNeeded(.workouts)
        return []
    }

    func fetchEcgSamples(days: Int) async throws -> [ECGRecord] {
        try failIfNeeded(.ecg)
        return ecgSamples
    }

    private func failIfNeeded(_ category: HealthExportCategory) throws {
        if failingCategories.contains(category) {
            throw CoordinatorTestError.expected
        }
    }
}

@MainActor
private final class FakeHealthExportIngestClient: HealthExportIngesting {
    var categories: [HealthExportCategory] = []
    var failingSourceIDs: Set<String> = []

    func ingestSleep(serverURL: URL, samples: [SleepSampleRecord]) async throws -> IngestResponse {
        response(for: .sleep, count: samples.count)
    }

    func ingestVitals(serverURL: URL, samples: [VitalsSampleRecord]) async throws -> IngestResponse {
        response(for: .vitals, count: samples.count)
    }

    func ingestBody(serverURL: URL, samples: [BodySampleRecord]) async throws -> IngestResponse {
        response(for: .body, count: samples.count)
    }

    func ingestLifestyle(serverURL: URL, samples: [LifestyleSampleRecord]) async throws -> IngestResponse {
        response(for: .lifestyle, count: samples.count)
    }

    func ingestActivity(serverURL: URL, samples: [ActivitySampleRecord]) async throws -> IngestResponse {
        response(for: .activity, count: samples.count)
    }

    func ingestWorkouts(serverURL: URL, samples: [WorkoutRecord]) async throws -> IngestResponse {
        response(for: .workouts, count: samples.count)
    }

    func ingestEcg(serverURL: URL, samples: [ECGRecord]) async throws -> IngestResponse {
        if let sourceID = samples.first?.sourceID, failingSourceIDs.contains(sourceID) {
            throw CoordinatorTestError.expected
        }
        return response(for: .ecg, count: samples.count)
    }

    private func response(for category: HealthExportCategory, count: Int) -> IngestResponse {
        categories.append(category)
        return IngestResponse(status: "accepted", upserted: count, totalSamples: count)
    }
}

private enum CoordinatorTestError: Error {
    case expected
}
