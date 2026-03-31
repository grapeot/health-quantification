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

    var body: some Scene {
        WindowGroup {
            ContentView(model: model, serverURL: $serverURL)
        }
    }
}
