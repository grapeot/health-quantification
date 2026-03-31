//
//  HealthQuantificationIOSApp.swift
//  HealthQuantificationIOS
//
//  Created by Yan Wang on 3/30/26.
//

import SwiftUI

@main
struct HealthQuantificationIOSApp: App {
    @AppStorage("serverURL") private var serverURL = "http://quantum.tail63c3c5.ts.net:7996"
    @State private var model = HealthKitService()

    var body: some Scene {
        WindowGroup {
            ContentView(model: model, serverURL: $serverURL)
        }
    }
}
