import Foundation
import HealthKit

enum ECGExportMapping {
    static let leadName = "apple_watch_similar_to_lead_i"
    static let voltageUnit = "V"
    static let emptyResultNote = "no samples returned; empty result does not prove absence or a normal classification"

    static let symptomTypeIdentifiers: [HKCategoryTypeIdentifier] = [
        .chestTightnessOrPain,
        .dizziness,
        .fainting,
        .fatigue,
        .rapidPoundingOrFlutteringHeartbeat,
        .shortnessOfBreath,
        .skippedHeartbeat,
    ]

    static func classificationName(rawValue: Int) -> String {
        switch rawValue {
        case HKElectrocardiogram.Classification.notSet.rawValue:
            return "not_set"
        case HKElectrocardiogram.Classification.sinusRhythm.rawValue:
            return "sinus_rhythm"
        case HKElectrocardiogram.Classification.atrialFibrillation.rawValue:
            return "atrial_fibrillation"
        case HKElectrocardiogram.Classification.inconclusiveLowHeartRate.rawValue:
            return "inconclusive_low_heart_rate"
        case HKElectrocardiogram.Classification.inconclusiveHighHeartRate.rawValue:
            return "inconclusive_high_heart_rate"
        case HKElectrocardiogram.Classification.inconclusivePoorReading.rawValue:
            return "inconclusive_poor_reading"
        case HKElectrocardiogram.Classification.inconclusiveOther.rawValue:
            return "inconclusive_other"
        case HKElectrocardiogram.Classification.unrecognized.rawValue:
            return "unrecognized"
        default:
            return "unrecognized_\(rawValue)"
        }
    }

    static func symptomsStatusName(rawValue: Int) -> String {
        switch rawValue {
        case HKElectrocardiogram.SymptomsStatus.notSet.rawValue:
            return "not_set"
        case HKElectrocardiogram.SymptomsStatus.none.rawValue:
            return "none"
        case HKElectrocardiogram.SymptomsStatus.present.rawValue:
            return "present"
        default:
            return "unrecognized_\(rawValue)"
        }
    }

    static func severityName(rawValue: Int) -> String {
        switch HKCategoryValueSeverity(rawValue: rawValue) {
        case .unspecified:
            return "unspecified"
        case .notPresent:
            return "not_present"
        case .mild:
            return "mild"
        case .moderate:
            return "moderate"
        case .severe:
            return "severe"
        default:
            return "unrecognized_\(rawValue)"
        }
    }

    static func symptomTypeName(_ identifier: HKCategoryTypeIdentifier) -> String {
        switch identifier {
        case .chestTightnessOrPain:
            return "chest_tightness_or_pain"
        case .dizziness:
            return "dizziness"
        case .fainting:
            return "fainting"
        case .fatigue:
            return "fatigue"
        case .rapidPoundingOrFlutteringHeartbeat:
            return "rapid_pounding_or_fluttering_heartbeat"
        case .shortnessOfBreath:
            return "shortness_of_breath"
        case .skippedHeartbeat:
            return "skipped_heartbeat"
        default:
            return "unrecognized_symptom"
        }
    }

    static func voltageAssessment(
        expectedCount: Int,
        voltages: [Double?],
        queryFailed: Bool
    ) -> (status: String, errorCode: String?) {
        if queryFailed && voltages.isEmpty {
            return ("query_failed", "voltage_query_failed")
        }
        if queryFailed {
            return ("partial", "voltage_query_failed")
        }
        if voltages.isEmpty {
            return ("unavailable", "voltage_unavailable")
        }
        let missingLead = voltages.contains { $0 == nil }
        if missingLead || voltages.count != expectedCount {
            return ("partial", missingLead ? "lead_voltage_missing" : "voltage_count_mismatch")
        }
        return ("complete", nil)
    }

    static func symptomsReadStatus(
        symptomsStatus: String,
        queried: Int,
        failed: Int,
        returned: Int
    ) -> String {
        guard symptomsStatus == "present" else {
            return "not_applicable"
        }
        if queried == 0 {
            return "unavailable"
        }
        if failed == queried {
            return "query_failed"
        }
        if failed > 0 {
            return "partial"
        }
        if returned == 0 {
            return "not_returned"
        }
        return "complete"
    }
}
