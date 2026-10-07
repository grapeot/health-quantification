import XCTest

final class HomeScreenShortcutUITests: XCTestCase {
    private let deadServerURL = "http://127.0.0.1:9"

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testWarmShortcutStartsSavedExport() throws {
        let app = configuredApp()
        app.launch()
        try assertSavedServer(in: app)

        let status = try triggerShortcut(expecting: app)
        XCTAssertNotEqual(status, "Idle")
        XCTAssertEqual(app.textFields["serverURLField"].value as? String, deadServerURL)
    }

    @MainActor
    func testColdShortcutStartsSavedExportWithoutLaunchArguments() throws {
        let app = configuredApp()
        app.launch()
        try assertSavedServer(in: app)
        app.terminate()

        let coldApp = XCUIApplication()
        let status = try triggerShortcut(expecting: coldApp)
        XCTAssertNotEqual(status, "Idle")
        XCTAssertEqual(coldApp.textFields["serverURLField"].value as? String, deadServerURL)
    }

    @MainActor
    private func waitForFieldValue(_ field: XCUIElement, expected: String) throws -> String {
        let deadline = Date().addingTimeInterval(5)
        var value = field.value as? String ?? ""
        while value != expected, Date() < deadline {
            RunLoop.current.run(until: Date().addingTimeInterval(0.2))
            value = field.value as? String ?? ""
        }
        return value
    }

    @MainActor
    private func configuredApp() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-UITEST_SERVER_URL", deadServerURL]
        return app
    }

    @MainActor
    private func assertSavedServer(in app: XCUIApplication) throws {
        let field = app.textFields["serverURLField"]
        XCTAssertTrue(field.waitForExistence(timeout: 8))
        XCTAssertEqual(try waitForFieldValue(field, expected: deadServerURL), deadServerURL)
    }

    @MainActor
    private func triggerShortcut(expecting app: XCUIApplication) throws -> String {
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let icon = revealIcon(in: springboard)
        XCTAssertTrue(icon.isHittable, "Home screen icon was not hittable: \(icon.frame)")
        icon.press(forDuration: 0.7)

        let action = shortcutAction(in: springboard)
        if !action.waitForExistence(timeout: 3) {
            attachScreenshot(named: "shortcut-menu-missing")
        }
        XCTAssertTrue(action.waitForExistence(timeout: 2), "Missing shortcut. Labels: \(menuLabels(in: springboard))")
        XCTAssertFalse(action.label.contains("http://") || action.label.contains("https://"))
        XCTAssertFalse(action.label.contains(deadServerURL))
        attachScreenshot(named: "shortcut-menu")
        action.tap()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 8))
        return try exportStatus(in: app)
    }

    @MainActor
    private func revealIcon(in springboard: XCUIApplication) -> XCUIElement {
        let icon = springboard.icons["HealthQuantificationIOS"]
        XCUIDevice.shared.press(.home)
        XCUIDevice.shared.press(.home)
        if waitUntilHittable(icon, timeout: 6) {
            return icon
        }
        for _ in 0..<4 {
            springboard.swipeLeft()
            if waitUntilHittable(icon, timeout: 2) {
                return icon
            }
        }
        return icon
    }

    @MainActor
    private func waitUntilHittable(_ icon: XCUIElement, timeout: TimeInterval) -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if icon.exists, icon.isHittable, icon.frame.width > 1 {
                return true
            }
            RunLoop.current.run(until: Date().addingTimeInterval(0.25))
        }
        return false
    }

    @MainActor
    private func shortcutAction(in springboard: XCUIApplication) -> XCUIElement {
        let predicate = NSPredicate(format: "label BEGINSWITH %@", "Transfer Now")
        let queries = [
            springboard.buttons.matching(predicate),
            springboard.menuItems.matching(predicate),
            springboard.cells.matching(predicate),
            springboard.staticTexts.matching(predicate),
        ]
        return queries.first { $0.firstMatch.exists }?.firstMatch
            ?? springboard.descendants(matching: .any).matching(predicate).firstMatch
    }

    @MainActor
    private func menuLabels(in springboard: XCUIApplication) -> String {
        let labels = springboard.buttons.allElementsBoundByIndex.prefix(12).map(\.label).filter { !$0.isEmpty }
        return labels.joined(separator: " | ")
    }

    @MainActor
    private func attachScreenshot(named name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    @MainActor
    private func exportStatus(in app: XCUIApplication) throws -> String {
        let status = app.staticTexts["exportStatusTitle"]
        if !status.waitForExistence(timeout: 2) {
            app.swipeUp()
        }
        XCTAssertTrue(status.waitForExistence(timeout: 8))
        let deadline = Date().addingTimeInterval(8)
        var label = status.label
        while label == "Idle", Date() < deadline {
            RunLoop.current.run(until: Date().addingTimeInterval(0.2))
            label = status.label
        }
        let shot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: shot)
        attachment.name = "export-status-\(label)"
        attachment.lifetime = .keepAlways
        add(attachment)
        return label
    }
}
