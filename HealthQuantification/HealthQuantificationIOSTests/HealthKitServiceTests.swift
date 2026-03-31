import Foundation
import HealthKit
import XCTest
@testable import HealthQuantificationIOS

final class HealthKitServiceTests: XCTestCase {
    @MainActor
    func testStageNameMapsAllKnownValuesAndUnknown() {
        XCTAssertEqual(HealthKitService.stageName(for: HKCategoryValueSleepAnalysis.inBed.rawValue), "in_bed")
        XCTAssertEqual(HealthKitService.stageName(for: HKCategoryValueSleepAnalysis.awake.rawValue), "awake")
        XCTAssertEqual(HealthKitService.stageName(for: HKCategoryValueSleepAnalysis.asleepCore.rawValue), "asleep_core")
        XCTAssertEqual(HealthKitService.stageName(for: HKCategoryValueSleepAnalysis.asleepDeep.rawValue), "asleep_deep")
        XCTAssertEqual(HealthKitService.stageName(for: HKCategoryValueSleepAnalysis.asleepREM.rawValue), "asleep_rem")
        XCTAssertEqual(HealthKitService.stageName(for: HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue), "asleep_unspecified")
        XCTAssertEqual(HealthKitService.stageName(for: -1), "unknown")
    }

    func testIsoTimestampUsesInternetDateTimeUTC() throws {
        var components = DateComponents()
        components.calendar = Calendar(identifier: .gregorian)
        components.timeZone = TimeZone(secondsFromGMT: 0)
        components.year = 2026
        components.month = 3
        components.day = 31
        components.hour = 2
        components.minute = 35
        components.second = 56

        let date = try XCTUnwrap(components.date)
        XCTAssertEqual(HealthKitService.isoTimestamp(date), "2026-03-31T02:35:56Z")
    }

    @MainActor
    func testNormalizedStageValueMapsAllKnownValuesAndUnknown() {
        XCTAssertEqual(HealthKitService.normalizedStageValue(for: HKCategoryValueSleepAnalysis.inBed.rawValue), 0)
        XCTAssertEqual(HealthKitService.normalizedStageValue(for: HKCategoryValueSleepAnalysis.awake.rawValue), 1)
        XCTAssertEqual(HealthKitService.normalizedStageValue(for: HKCategoryValueSleepAnalysis.asleepCore.rawValue), 2)
        XCTAssertEqual(HealthKitService.normalizedStageValue(for: HKCategoryValueSleepAnalysis.asleepDeep.rawValue), 3)
        XCTAssertEqual(HealthKitService.normalizedStageValue(for: HKCategoryValueSleepAnalysis.asleepREM.rawValue), 4)
        XCTAssertEqual(HealthKitService.normalizedStageValue(for: HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue), 5)
        XCTAssertEqual(HealthKitService.normalizedStageValue(for: -1), -1)
    }
}
