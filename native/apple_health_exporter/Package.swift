// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "apple_health_exporter",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .executable(name: "apple_health_exporter", targets: ["apple_health_exporter"]),
    ],
    targets: [
        .executableTarget(
            name: "apple_health_exporter",
            path: "Sources"
        ),
    ]
)
