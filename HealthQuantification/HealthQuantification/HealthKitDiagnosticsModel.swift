import Foundation
import HealthKit
import Observation

@Observable
final class HealthKitDiagnosticsModel {
    var healthDataAvailableText = "unknown"
    var authorizationState = "not_requested"
    var lastUpdated = "never"
    var logEntries: [String] = []

    private let healthStore = HKHealthStore()

    var logText: String {
        logEntries.joined(separator: "\n\n")
    }

    func runDoctor() {
        let available = HKHealthStore.isHealthDataAvailable()
        healthDataAvailableText = available ? "true" : "false"
        lastUpdated = isoTimestamp(Date())
        appendLog(
            title: "doctor",
            payload: [
                "platform": "macOS",
                "healthDataAvailable": healthDataAvailableText,
                "timestamp": lastUpdated,
            ]
        )
    }

    func requestSleepAccess() {
        runDoctor()

        guard HKHealthStore.isHealthDataAvailable() else {
            authorizationState = "health_data_unavailable"
            appendLog(
                title: "requestSleepAccess",
                payload: ["result": authorizationState]
            )
            return
        }

        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else {
            authorizationState = "sleep_type_unavailable"
            appendLog(
                title: "requestSleepAccess",
                payload: ["result": authorizationState]
            )
            return
        }

        healthStore.requestAuthorization(toShare: [], read: [sleepType]) { success, error in
            DispatchQueue.main.async {
                self.lastUpdated = self.isoTimestamp(Date())
                if let error {
                    self.authorizationState = "error"
                    self.appendLog(
                        title: "requestSleepAccess",
                        payload: [
                            "error": String(describing: error),
                            "timestamp": self.lastUpdated,
                        ]
                    )
                    return
                }

                self.authorizationState = success ? "granted" : "denied"
                self.appendLog(
                    title: "requestSleepAccess",
                    payload: [
                        "result": self.authorizationState,
                        "timestamp": self.lastUpdated,
                    ]
                )
            }
        }
    }

    private func appendLog(title: String, payload: [String: String]) {
        let data = try? JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys])
        let text = String(data: data ?? Data("{}".utf8), encoding: .utf8) ?? "{}"
        let block = "[\(title)]\n\(text)"
        logEntries.append(block)
        print(block)
    }

    private func isoTimestamp(_ date: Date) -> String {
        ISO8601DateFormatter().string(from: date)
    }
}
