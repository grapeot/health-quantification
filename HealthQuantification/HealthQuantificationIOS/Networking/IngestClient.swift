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

    private func ingest<Sample: Codable & Equatable>(samples: [Sample], endpointName: String, serverURL: URL) async throws -> IngestResponse {
        let endpoint = serverURL.appending(path: "ingest").appending(path: endpointName)
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = try JSONEncoder().encode(IngestEnvelope(samples: samples))

        do {
            let (data, response) = try await session.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw IngestClientError.invalidResponse
            }

            guard (200 ... 299).contains(httpResponse.statusCode) else {
                let message = String(data: data, encoding: .utf8)
                throw IngestClientError.serverError(statusCode: httpResponse.statusCode, message: message)
            }

            do {
                return try JSONDecoder().decode(IngestResponse.self, from: data)
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
                return "Server error \(statusCode): \(message)"
            }
            return "Server error \(statusCode)."
        case let .decodingFailed(error):
            return "Failed to decode server response: \(error.localizedDescription)"
        case let .networkFailed(error):
            return "Network request failed: \(error.localizedDescription)"
        }
    }
}
