import SwiftUI

@main
struct HealthQuantificationIOSApp: App {
    @UIApplicationDelegateAdaptor(HealthQuantificationAppDelegate.self) private var appDelegate

    var body: some Scene {
        ExportShortcutSceneDelegate.rootScene
    }
}
