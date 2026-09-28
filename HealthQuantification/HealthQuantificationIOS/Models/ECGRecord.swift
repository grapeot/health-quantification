import Foundation

struct ECGVoltagePoint: Codable, Equatable {
    let timeOffsetSeconds: Double
    let voltageVolts: Double?

    enum CodingKeys: String, CodingKey {
        case timeOffsetSeconds = "time_offset_seconds"
        case voltageVolts = "voltage_volts"
    }
}

struct ECGSymptomRecord: Codable, Equatable {
    let symptomType: String
    let severity: String
    let severityValue: Int
    let sourceID: String

    enum CodingKeys: String, CodingKey {
        case symptomType = "symptom_type"
        case severity
        case severityValue = "severity_value"
        case sourceID = "source_id"
    }
}

struct ECGRecord: Codable, Equatable {
    let sourceID: String
    let startAt: String
    let endAt: String
    let algorithmClassification: String
    let algorithmClassificationValue: Int
    let symptomsStatus: String
    let symptomsStatusValue: Int
    let averageHeartRateBPM: Double?
    let samplingFrequencyHz: Double?
    let numberOfVoltageMeasurements: Int
    let voltageCount: Int
    let voltageUnit: String?
    let lead: String
    let voltageStatus: String
    let voltageErrorCode: String?
    let algorithmVersion: Int?
    let sourceBundleID: String
    let sourceName: String
    let symptoms: [ECGSymptomRecord]
    let symptomsReadStatus: String
    let metadata: [String: String]
    let voltage: [ECGVoltagePoint]

    enum CodingKeys: String, CodingKey {
        case sourceID = "source_id"
        case startAt = "start_at"
        case endAt = "end_at"
        case algorithmClassification = "algorithm_classification"
        case algorithmClassificationValue = "algorithm_classification_value"
        case symptomsStatus = "symptoms_status"
        case symptomsStatusValue = "symptoms_status_value"
        case averageHeartRateBPM = "average_heart_rate_bpm"
        case samplingFrequencyHz = "sampling_frequency_hz"
        case numberOfVoltageMeasurements = "number_of_voltage_measurements"
        case voltageCount = "voltage_count"
        case voltageUnit = "voltage_unit"
        case lead
        case voltageStatus = "voltage_status"
        case voltageErrorCode = "voltage_error_code"
        case algorithmVersion = "algorithm_version"
        case sourceBundleID = "source_bundle_id"
        case sourceName = "source_name"
        case symptoms
        case symptomsReadStatus = "symptoms_read_status"
        case metadata
        case voltage
    }
}
