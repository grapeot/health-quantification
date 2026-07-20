import Foundation

@MainActor
protocol HealthExportDataSource {
    func fetchSleepSamples(days: Int) async throws -> [SleepSampleRecord]
    func fetchVitalsSamples(days: Int) async throws -> [VitalsSampleRecord]
    func fetchBodySamples(days: Int) async throws -> [BodySampleRecord]
    func fetchLifestyleSamples(days: Int) async throws -> [LifestyleSampleRecord]
    func fetchActivitySamples(days: Int) async throws -> [ActivitySampleRecord]
    func fetchWorkoutSamples(days: Int) async throws -> [WorkoutRecord]
}

@MainActor
protocol HealthExportIngesting {
    func ingestSleep(serverURL: URL, samples: [SleepSampleRecord]) async throws -> IngestResponse
    func ingestVitals(serverURL: URL, samples: [VitalsSampleRecord]) async throws -> IngestResponse
    func ingestBody(serverURL: URL, samples: [BodySampleRecord]) async throws -> IngestResponse
    func ingestLifestyle(serverURL: URL, samples: [LifestyleSampleRecord]) async throws -> IngestResponse
    func ingestActivity(serverURL: URL, samples: [ActivitySampleRecord]) async throws -> IngestResponse
    func ingestWorkouts(serverURL: URL, samples: [WorkoutRecord]) async throws -> IngestResponse
}

extension HealthKitService: HealthExportDataSource {}
extension IngestClient: HealthExportIngesting {}

@MainActor
struct HealthExportCoordinator {
    let dataSource: any HealthExportDataSource
    let ingestClient: any HealthExportIngesting

    func exportAll(serverURL: URL, days: Int = 30) async -> HealthExportResult {
        var results: [HealthExportCategoryResult] = []

        do {
            let samples = try await dataSource.fetchSleepSamples(days: days)
            let response = try await ingestClient.ingestSleep(serverURL: serverURL, samples: samples)
            results.append(.success(.sleep, sent: samples.count, upserted: response.upserted))
        } catch {
            results.append(.failure(.sleep, error: error))
        }

        do {
            let samples = try await dataSource.fetchVitalsSamples(days: days)
            let response = try await ingestClient.ingestVitals(serverURL: serverURL, samples: samples)
            results.append(.success(.vitals, sent: samples.count, upserted: response.upserted))
        } catch {
            results.append(.failure(.vitals, error: error))
        }

        do {
            let samples = try await dataSource.fetchBodySamples(days: days)
            if samples.isEmpty {
                results.append(.success(.body, sent: 0, upserted: 0))
            } else {
                let response = try await ingestClient.ingestBody(serverURL: serverURL, samples: samples)
                results.append(.success(.body, sent: samples.count, upserted: response.upserted))
            }
        } catch {
            results.append(.failure(.body, error: error))
        }

        do {
            let samples = try await dataSource.fetchLifestyleSamples(days: days)
            if samples.isEmpty {
                results.append(.success(.lifestyle, sent: 0, upserted: 0))
            } else {
                let response = try await ingestClient.ingestLifestyle(serverURL: serverURL, samples: samples)
                results.append(.success(.lifestyle, sent: samples.count, upserted: response.upserted))
            }
        } catch {
            results.append(.failure(.lifestyle, error: error))
        }

        do {
            let samples = try await dataSource.fetchActivitySamples(days: days)
            let response = try await ingestClient.ingestActivity(serverURL: serverURL, samples: samples)
            results.append(.success(.activity, sent: samples.count, upserted: response.upserted))
        } catch {
            results.append(.failure(.activity, error: error))
        }

        do {
            let samples = try await dataSource.fetchWorkoutSamples(days: days)
            let response = try await ingestClient.ingestWorkouts(serverURL: serverURL, samples: samples)
            results.append(.success(.workouts, sent: samples.count, upserted: response.upserted))
        } catch {
            results.append(.failure(.workouts, error: error))
        }

        return .aggregate(results)
    }
}
