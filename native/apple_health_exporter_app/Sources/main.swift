import AppKit
import Foundation
import HealthKit

final class HealthStatusController {
    private let healthStore = HKHealthStore()

    func doctorPayload() -> [String: String] {
        [
            "platform": "macOS",
            "healthDataAvailable": HKHealthStore.isHealthDataAvailable() ? "true" : "false",
            "timestamp": ISO8601DateFormatter().string(from: Date()),
        ]
    }

    func requestSleepReadAuthorization(completion: @escaping (Result<String, Error>) -> Void) {
        guard HKHealthStore.isHealthDataAvailable() else {
            completion(.success("healthDataAvailable=false"))
            return
        }
        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else {
            completion(.success("sleepTypeUnavailable"))
            return
        }

        healthStore.requestAuthorization(toShare: [], read: [sleepType]) { success, error in
            if let error {
                completion(.failure(error))
                return
            }
            completion(.success(success ? "authorizationGranted" : "authorizationDenied"))
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private let controller = HealthStatusController()
    private var window: NSWindow?
    private var statusLabel: NSTextField?
    private var outputView: NSTextView?

    func applicationDidFinishLaunching(_ notification: Notification) {
        createWindow()
        refreshDoctorStatus()
    }

    private func createWindow() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 720, height: 440),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.center()
        window.title = "Apple Health Exporter App"

        let root = NSView(frame: window.contentView?.bounds ?? .zero)
        root.autoresizingMask = [.width, .height]

        let titleLabel = NSTextField(labelWithString: "Apple Health Exporter App Shell")
        titleLabel.font = .boldSystemFont(ofSize: 24)
        titleLabel.frame = NSRect(x: 24, y: 380, width: 500, height: 32)

        let statusLabel = NSTextField(labelWithString: "status: loading")
        statusLabel.font = .monospacedSystemFont(ofSize: 14, weight: .regular)
        statusLabel.frame = NSRect(x: 24, y: 345, width: 600, height: 24)
        self.statusLabel = statusLabel

        let doctorButton = NSButton(title: "Run Doctor", target: self, action: #selector(runDoctor))
        doctorButton.frame = NSRect(x: 24, y: 300, width: 140, height: 32)

        let authButton = NSButton(title: "Request Sleep Access", target: self, action: #selector(requestSleepAccess))
        authButton.frame = NSRect(x: 176, y: 300, width: 180, height: 32)

        let scrollView = NSScrollView(frame: NSRect(x: 24, y: 24, width: 672, height: 252))
        scrollView.hasVerticalScroller = true
        scrollView.borderType = .bezelBorder

        let outputView = NSTextView(frame: scrollView.bounds)
        outputView.isEditable = false
        outputView.font = .monospacedSystemFont(ofSize: 13, weight: .regular)
        outputView.string = "Waiting for action..."
        scrollView.documentView = outputView
        self.outputView = outputView

        root.addSubview(titleLabel)
        root.addSubview(statusLabel)
        root.addSubview(doctorButton)
        root.addSubview(authButton)
        root.addSubview(scrollView)

        window.contentView = root
        window.makeKeyAndOrderFront(nil)
        self.window = window
    }

    private func refreshDoctorStatus() {
        let payload = controller.doctorPayload()
        statusLabel?.stringValue = "status: healthDataAvailable=\(payload["healthDataAvailable"] ?? "unknown")"
        appendOutput(title: "doctor", payload: payload)
    }

    @objc private func runDoctor() {
        refreshDoctorStatus()
    }

    @objc private func requestSleepAccess() {
        appendOutput(title: "requestSleepAccess", payload: ["status": "requesting"])
        controller.requestSleepReadAuthorization { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case let .success(message):
                    self?.appendOutput(title: "requestSleepAccess", payload: ["result": message])
                case let .failure(error):
                    self?.appendOutput(title: "requestSleepAccess", payload: ["error": String(describing: error)])
                }
            }
        }
    }

    private func appendOutput(title: String, payload: [String: String]) {
        let data = try? JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys])
        let text = String(data: data ?? Data(), encoding: .utf8) ?? "{}"
        let block = "[\(title)]\n\(text)\n\n"
        outputView?.string += block
        Swift.print(block)
    }
}

let application = NSApplication.shared
let delegate = AppDelegate()
application.setActivationPolicy(.regular)
application.delegate = delegate
application.run()
