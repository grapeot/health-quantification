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
    @State private var exportAllDeepLinkTrigger = 0

    var body: some Scene {
        WindowGroup {
            ContentView(
                model: model,
                serverURL: $serverURL,
                exportAllDeepLinkTrigger: $exportAllDeepLinkTrigger
            )
            .onOpenURL { url in
                handleDeepLink(url)
            }
        }
    }

    private func handleDeepLink(_ url: URL) {
        guard url.scheme == "healthquantification" else {
            return
        }

        let normalizedAction = [url.host, url.path]
            .compactMap { $0 }
            .joined(separator: "/")
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            .lowercased()

        if normalizedAction == "export-all" || normalizedAction == "export/all" {
            exportAllDeepLinkTrigger += 1
        }
    }
}
