// Local Apple Vision OCR. Usage: swift ocr_labels.swift image.jpg [image2.jpg ...]
import Foundation
import Vision
import AppKit
for path in CommandLine.arguments.dropFirst() {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    do {
        try VNImageRequestHandler(url: URL(fileURLWithPath: path)).perform([request])
        let lines = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
        let data = try JSONSerialization.data(withJSONObject: ["path": path, "lines": lines], options: [.sortedKeys])
        print(String(data: data, encoding: .utf8)!)
    } catch {
        fputs("OCR failed for \(path): \(error)\n", stderr)
        exit(1)
    }
}
