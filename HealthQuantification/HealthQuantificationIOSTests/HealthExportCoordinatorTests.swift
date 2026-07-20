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
}

@MainActor
private final class FakeHealthExportDataSource: HealthExportDataSource {
    let failingCategories: Set<HealthExportCategory>

    init(failingCategories: Set<HealthExportCategory> = []) {
        self.failingCategories = failingCategories
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

    private func failIfNeeded(_ category: HealthExportCategory) throws {
        if failingCategories.contains(category) {
            throw CoordinatorTestError.expected
        }
    }
}

@MainActor
private final class FakeHealthExportIngestClient: HealthExportIngesting {
    var categories: [HealthExportCategory] = []

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

    private func response(for category: HealthExportCategory, count: Int) -> IngestResponse {
        categories.append(category)
        return IngestResponse(status: "accepted", upserted: count, totalSamples: count)
    }
}

private enum CoordinatorTestError: Error {
    case expected
}
