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
    func testDoctorAndRequestSleepAccessFlow() throws {
        let app = XCUIApplication()
        app.launchArguments.append("UITEST_HEALTH_DATA_AVAILABLE_TRUE")
        app.launch()

        app.buttons["runDoctorButton"].tap()
        XCTAssertTrue(app.staticTexts["healthDataAvailableLabel"].waitForExistence(timeout: 2))
        XCTAssertTrue(app.staticTexts["healthDataAvailable: true"].waitForExistence(timeout: 2))

        app.buttons["requestSleepAccessButton"].tap()
        XCTAssertTrue(app.staticTexts["authorizationStateLabel"].waitForExistence(timeout: 2))
    }

    @MainActor
    func testLaunchPerformance() throws {
        // This measures how long it takes to launch your application.
        measure(metrics: [XCTApplicationLaunchMetric()]) {
            XCUIApplication().launch()
        }
    }
}
