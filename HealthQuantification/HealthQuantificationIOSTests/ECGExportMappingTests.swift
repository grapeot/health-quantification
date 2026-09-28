import HealthKit
import XCTest
@testable import HealthQuantificationIOS

final class ECGExportMappingTests: XCTestCase {
    func testClassificationNamesMatchAlgorithmEnumAndAreNotDiagnosisLabels() {
        XCTAssertEqual(
            ECGExportMapping.classificationName(rawValue: HKElectrocardiogram.Classification.notSet.rawValue),
            "not_set"
        )
        XCTAssertEqual(
            ECGExportMapping.classificationName(rawValue: HKElectrocardiogram.Classification.sinusRhythm.rawValue),
            "sinus_rhythm"
        )
        XCTAssertEqual(
            ECGExportMapping.classificationName(rawValue: HKElectrocardiogram.Classification.atrialFibrillation.rawValue),
            "atrial_fibrillation"
        )
        XCTAssertEqual(
            ECGExportMapping.classificationName(rawValue: HKElectrocardiogram.Classification.inconclusiveLowHeartRate.rawValue),
            "inconclusive_low_heart_rate"
        )
        XCTAssertEqual(
            ECGExportMapping.classificationName(rawValue: HKElectrocardiogram.Classification.inconclusiveHighHeartRate.rawValue),
            "inconclusive_high_heart_rate"
        )
        XCTAssertEqual(
            ECGExportMapping.classificationName(rawValue: HKElectrocardiogram.Classification.inconclusivePoorReading.rawValue),
            "inconclusive_poor_reading"
        )
        XCTAssertEqual(
            ECGExportMapping.classificationName(rawValue: HKElectrocardiogram.Classification.inconclusiveOther.rawValue),
            "inconclusive_other"
        )
        XCTAssertEqual(
            ECGExportMapping.classificationName(rawValue: HKElectrocardiogram.Classification.unrecognized.rawValue),
            "unrecognized"
        )
        XCTAssertEqual(ECGExportMapping.classificationName(rawValue: 101), "unrecognized_101")
    }

    func testSymptomsStatusNamesMatchOfficialValues() {
        XCTAssertEqual(
            ECGExportMapping.symptomsStatusName(rawValue: HKElectrocardiogram.SymptomsStatus.notSet.rawValue),
            "not_set"
        )
        XCTAssertEqual(
            ECGExportMapping.symptomsStatusName(rawValue: HKElectrocardiogram.SymptomsStatus.none.rawValue),
            "none"
        )
        XCTAssertEqual(
            ECGExportMapping.symptomsStatusName(rawValue: HKElectrocardiogram.SymptomsStatus.present.rawValue),
            "present"
        )
    }

    func testVoltageAssessmentDistinguishesUnavailablePartialAndComplete() {
        XCTAssertEqual(
            ECGExportMapping.voltageAssessment(expectedCount: 2, voltages: [], queryFailed: false).status,
            "unavailable"
        )
        XCTAssertEqual(
            ECGExportMapping.voltageAssessment(expectedCount: 2, voltages: [], queryFailed: true).status,
            "query_failed"
        )
        XCTAssertEqual(
            ECGExportMapping.voltageAssessment(expectedCount: 2, voltages: [0.1, nil], queryFailed: false).status,
            "partial"
        )
        XCTAssertEqual(
            ECGExportMapping.voltageAssessment(expectedCount: 2, voltages: [0.1], queryFailed: true).status,
            "partial"
        )
        XCTAssertEqual(
            ECGExportMapping.voltageAssessment(expectedCount: 2, voltages: [0.1, -0.2], queryFailed: false).status,
            "complete"
        )
    }

    func testPresentSymptomsWithNoAssociatedSamplesAreNotTreatedAsNone() {
        XCTAssertEqual(
            ECGExportMapping.symptomsReadStatus(symptomsStatus: "none", queried: 0, failed: 0, returned: 0),
            "not_applicable"
        )
        XCTAssertEqual(
            ECGExportMapping.symptomsReadStatus(symptomsStatus: "present", queried: 7, failed: 0, returned: 0),
            "not_returned"
        )
        XCTAssertEqual(
            ECGExportMapping.symptomsReadStatus(symptomsStatus: "present", queried: 7, failed: 7, returned: 0),
            "query_failed"
        )
        XCTAssertEqual(
            ECGExportMapping.symptomsReadStatus(symptomsStatus: "present", queried: 7, failed: 1, returned: 1),
            "partial"
        )
    }
}