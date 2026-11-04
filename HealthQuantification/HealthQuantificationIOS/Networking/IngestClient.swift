import Foundation

struct IngestClient {
    private let session: URLSession
    private let onVitalsProgress: (@MainActor @Sendable (Int, Int) -> Void)?

    init(session: URLSession = .shared, onVitalsProgress: (@MainActor @Sendable (Int, Int) -> Void)? = nil) {
        self.session = session
        self.onVitalsProgress = onVitalsProgress
    }

    func ingestSleep(serverURL: URL, samples: [SleepSampleRecord]) async throws -> IngestResponse {
        try await ingest(samples: samples, endpointName: "sleep", serverURL: serverURL)
    }

    func ingestVitals(serverURL: URL, samples: [VitalsSampleRecord]) async throws -> IngestResponse {
        // Bound each request rather than raising the timeout for a whole 30-day payload.
        // Source IDs make an interrupted export safe to send again.
        guard !samples.isEmpty else {
            return try await ingest(samples: samples, endpointName: "vitals", serverURL: serverURL)
        }
        var accepted = 0
        var lastResponse: IngestResponse?
        onVitalsProgress?(0, samples.count)
        for start in stride(from: 0, to: samples.count, by: 2_000) {
            let end = min(start + 2_000, samples.count)
            let response: IngestResponse
            do {
                response = try await ingest(
                    samples: Array(samples[start..<end]), endpointName: "vitals", serverURL: serverURL
                )
            } catch {
                throw VitalsBatchUploadError(acknowledged: start, upserted: accepted,
                                            failedBatch: start / 2_000 + 1, underlying: error)
            }
            accepted += response.upserted
            lastResponse = response
            onVitalsProgress?(end, samples.count)
        }
        return IngestResponse(status: lastResponse!.status, upserted: accepted, totalSamples: lastResponse!.totalSamples)
    }

    func ingestBody(serverURL: URL, samples: [BodySampleRecord]) async throws -> IngestResponse {
        try await ingest(samples: samples, endpointName: "body", serverURL: serverURL)
    }

    func ingestLifestyle(serverURL: URL, samples: [LifestyleSampleRecord]) async throws -> IngestResponse {
        try await ingest(samples: samples, endpointName: "lifestyle", serverURL: serverURL)
    }

    func ingestActivity(serverURL: URL, samples: [ActivitySampleRecord]) async throws -> IngestResponse {
        try await ingest(samples: samples, endpointName: "activity", serverURL: serverURL)
    }

    func ingestWorkouts(serverURL: URL, samples: [WorkoutRecord]) async throws -> IngestResponse {
        try await ingest(samples: samples, endpointName: "workouts", serverURL: serverURL)
    }

    func ingestEcg(serverURL: URL, samples: [ECGRecord]) async throws -> IngestResponse {
        try await ingest(samples: samples, endpointName: "ecg", serverURL: serverURL)
    }

    private func ingest<Sample: Codable & Equatable>(samples: [Sample], endpointName: String, serverURL: URL) async throws -> IngestResponse {
        let endpoint = serverURL.appending(path: "ingest").appending(path: endpointName)
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let encodeStart = ExportProfiler.now()
        request.httpBody = try JSONEncoder().encode(IngestEnvelope(samples: samples))
        let profiler = ExportProfiler.current
        profiler?.record("\(endpointName).encode", since: encodeStart, count: samples.count, bytes: request.httpBody?.count)
        if let profiler { request.setValue(profiler.runID.uuidString, forHTTPHeaderField: "X-Health-Profile") }

        do {
            let httpStart = ExportProfiler.now()
            let delegate = profiler.map { ExportNetworkMetrics(profiler: $0, category: endpointName) }
            let (data, response) = try await session.data(for: request, delegate: delegate)
            profiler?.record("\(endpointName).http", since: httpStart)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw IngestClientError.invalidResponse
            }
            if let timing = httpResponse.value(forHTTPHeaderField: "Server-Timing") {
                for item in timing.split(separator: ",") {
                    let parts = item.trimmingCharacters(in: .whitespaces).split(separator: ";")
                    if parts.count == 2, ["initialize", "convert", "upsert", "count", "total"].contains(String(parts[0])),
                       parts[1].hasPrefix("dur="), let duration = Double(parts[1].dropFirst(4)), duration.isFinite, duration >= 0 {
                        profiler?.add("\(endpointName).server.\(parts[0])", milliseconds: duration)
                    }
                }
            }

            guard (200 ... 299).contains(httpResponse.statusCode) else {
                if endpointName == "ecg" {
                    throw IngestClientError.serverError(statusCode: httpResponse.statusCode, message: nil)
                }
                let message = String(data: data, encoding: .utf8)
                throw IngestClientError.serverError(statusCode: httpResponse.statusCode, message: message)
            }

            do {
                let result = try JSONDecoder().decode(IngestResponse.self, from: data)
                profiler?.add("\(endpointName).ingested", milliseconds: 0, count: result.upserted)
                return result
            } catch {
                throw IngestClientError.decodingFailed(error)
            }
        } catch let error as IngestClientError {
            throw error
        } catch {
            throw IngestClientError.networkFailed(error)
        }
    }
}

struct VitalsBatchUploadError: LocalizedError {
    let acknowledged: Int
    let upserted: Int
    let failedBatch: Int
    let underlying: Error

    var errorDescription: String? {
        "Batch \(failedBatch) failed after \(acknowledged) acknowledged samples (\(upserted) upserted); failed batch outcome unconfirmed. \(underlying.localizedDescription)"
    }
}

enum IngestClientError: LocalizedError {
    case invalidResponse
    case serverError(statusCode: Int, message: String?)
    case decodingFailed(Error)
    case networkFailed(Error)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "The server returned an invalid response."
        case let .serverError(statusCode, message):
            if let message, !message.isEmpty {
                let clipped = message.count > 180 ? String(message.prefix(180)) : message
                return "Server error \(statusCode): \(clipped)"
            }
            return "Server error \(statusCode)."
        case let .decodingFailed(error):
            return "Failed to decode server response: \(error.localizedDescription)"
        case let .networkFailed(error):
            return "Network request failed: \(error.localizedDescription)"
        }
    }
}
