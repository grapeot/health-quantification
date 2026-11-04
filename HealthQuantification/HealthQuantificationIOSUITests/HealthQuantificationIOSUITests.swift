//
//  HealthQuantificationIOSUITests.swift
//  HealthQuantificationIOSUITests
//
//  Created by Yan Wang on 3/30/26.
//

import XCTest

final class HealthQuantificationIOSUITests: XCTestCase {

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.

        // In UI tests it is usually best to stop immediately when a failure occurs.
        continueAfterFailure = false

        // In UI tests it’s important to set the initial state - such as interface orientation - required for your tests before they run. The setUp method is a good place to do this.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    @MainActor
    func testDoctorAndRequestHealthAccessFlow() throws {
        let app = XCUIApplication()
        app.launchArguments.append("UITEST_HEALTH_DATA_AVAILABLE_TRUE")
        app.launch()

        XCTAssertFalse(app.buttons["typeAuditButton"].exists)
        XCTAssertFalse(app.buttons["checkVitalsButton"].exists)
        XCTAssertTrue(app.buttons["exportAllButton"].exists)

        app.buttons["runDoctorButton"].tap()
        XCTAssertTrue(app.staticTexts["healthDataAvailableLabel"].waitForExistence(timeout: 2))
        XCTAssertTrue(app.staticTexts["Available"].waitForExistence(timeout: 2))

        app.buttons["requestHealthAccessButton"].tap()
        XCTAssertTrue(app.staticTexts["authorizationStateLabel"].waitForExistence(timeout: 2))
    }

    @MainActor
    func testExportProgressShowsStageAndSampleCounts() throws {
        let app = XCUIApplication()
        app.launchArguments = ["UITEST_HEALTH_DATA_AVAILABLE_TRUE", "UITEST_EXPORT_PROGRESS"]
        app.launch()
        let label = app.staticTexts["exportProgressLabel"]
        XCTAssertTrue(label.waitForExistence(timeout: 5))
        for _ in 0..<3 where !label.isHittable { app.swipeUp() }
        XCTAssertTrue(label.isHittable)
        XCTAssertEqual(label.label, "2 / 7 · vitals · 36,000 / 72,000 samples")
        XCTAssertTrue(app.progressIndicators["exportProgressBar"].exists)
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = "Export progress"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    @MainActor
    func testLaunchPerformance() throws {
        // This measures how long it takes to launch your application.
        measure(metrics: [XCTApplicationLaunchMetric()]) {
            XCUIApplication().launch()
        }
    }
}
