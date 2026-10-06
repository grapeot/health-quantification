import Foundation

struct IngestClient {
    private let session: URLSession

    init(session: URLSession = .shared) {
        self.session = session
    }

    func ingestSleep(serverURL: URL, samples: [SleepSampleRecord]) async throws -> IngestResponse {
        try await ingest(samples: samples, endpointName: "sleep", serverURL: serverURL)
    }

    func ingestVitals(serverURL: URL, samples: [VitalsSampleRecord]) async throws -> IngestResponse {
        try await ingest(samples: samples, endpointName: "vitals", serverURL: serverURL)
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
