//
//  HealthQuantificationIOSApp.swift
//  HealthQuantificationIOS
//
//  Created by Yan Wang on 3/30/26.
//

import SwiftUI

@main
struct HealthQuantificationIOSApp: App {
    @AppStorage("serverURL") private var serverURL = "http://localhost:7996"
    @State private var model = HealthKitService()
    @State private var exportRuntime = HealthExportRuntime()
    @State private var exportCommands: [HealthExportCommand] = []

    var body: some Scene {
        WindowGroup {
            ContentView(
                model: model,
                exportRuntime: $exportRuntime,
                serverURL: $serverURL,
                exportCommands: $exportCommands
            )
            .onOpenURL { url in
                handleDeepLink(url)
            }
        }
    }

    private func handleDeepLink(_ url: URL) {
        if let command = HealthExportDeepLinkParser.parse(url) {
            exportCommands.append(command)
            return
        }
        #if DEBUG
        if let command = HealthDiagnosticDeepLinkParser.parse(url) {
            Task {
                let result = await model.physicalEffortDiagnostic(command)
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
