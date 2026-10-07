import Observation
import SwiftUI
import UIKit

final class HealthQuantificationAppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        configurationForConnecting connectingSceneSession: UISceneSession,
        options: UIScene.ConnectionOptions
    ) -> UISceneConfiguration {
        _ = options
        let configuration = UISceneConfiguration(name: nil, sessionRole: connectingSceneSession.role)
        configuration.delegateClass = ExportShortcutSceneDelegate.self
        return configuration
    }
}

@MainActor
@Observable
final class HealthAppSession {
    static let shared = HealthAppSession()

    var model = HealthKitService()
    var exportRuntime = HealthExportRuntime()
    var exportCommands: [HealthExportCommand] = []
}

final class ExportShortcutSceneDelegate: NSObject, UIHostingSceneDelegate, UIWindowSceneDelegate {
    static var rootScene: some Scene {
        WindowGroup {
            HealthQuantificationRoot(session: .shared)
        }
    }

    func scene(
        _ scene: UIScene,
        willConnectTo session: UISceneSession,
        options connectionOptions: UIScene.ConnectionOptions
    ) {
        if let shortcutItem = connectionOptions.shortcutItem {
            _ = HomeScreenExportRouter.shared.accept(shortcutItem)
        }
    }

    func windowScene(
        _ windowScene: UIWindowScene,
        performActionFor shortcutItem: UIApplicationShortcutItem,
        completionHandler: @escaping (Bool) -> Void
    ) {
        completionHandler(HomeScreenExportRouter.shared.accept(shortcutItem))
    }
}

struct HealthQuantificationRoot: View {
    @AppStorage("serverURL") private var serverURL = "http://localhost:7996"
    @Bindable var session: HealthAppSession

    var body: some View {
        ContentView(
            model: session.model,
            exportRuntime: $session.exportRuntime,
            serverURL: $serverURL,
            exportCommands: $session.exportCommands
        )
        .onOpenURL { url in
            handleDeepLink(url)
        }
        #if DEBUG && targetEnvironment(simulator)
        .onAppear {
            if let value = Self.uiTestServerURL, serverURL != value {
                serverURL = value
            }
        }
        #endif
    }

    #if DEBUG && targetEnvironment(simulator)
    private static var uiTestServerURL: String? {
        let arguments = ProcessInfo.processInfo.arguments
        guard let flag = arguments.firstIndex(of: "-UITEST_SERVER_URL") else { return nil }
        let valueIndex = arguments.index(after: flag)
        guard arguments.indices.contains(valueIndex) else { return nil }
        let value = arguments[valueIndex]
        return HealthExportServerURLParser.parse(value) == nil ? nil : value
    }
    #endif

    private func handleDeepLink(_ url: URL) {
        if let command = HealthExportDeepLinkParser.parse(url) {
            session.exportCommands.append(command)
            return
        }
        #if DEBUG
        if let command = HealthDiagnosticDeepLinkParser.parse(url) {
            Task {
                let result = await session.model.physicalEffortDiagnostic(command)
                do {
                    _ = try HealthDiagnosticArtifactStore.save(result)
                } catch {
                    print("[diagnostic] artifact_write_failed")
                }
            }
        }
        #endif
    }
}
