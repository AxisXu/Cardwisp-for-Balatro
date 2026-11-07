import AppKit
import CoreGraphics
import WebKit

private func balatroFrame() -> CGRect? {
    guard let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else { return nil }
    let mainHeight = CGDisplayBounds(CGMainDisplayID()).height
    for window in windows {
        guard let owner = window[kCGWindowOwnerName as String] as? String,
              owner == "Balatro",
              let layer = window[kCGWindowLayer as String] as? Int, layer == 0,
              let raw = window[kCGWindowBounds as String] as? [String: Any],
              let bounds = CGRect(dictionaryRepresentation: raw as CFDictionary),
              bounds.width > 400, bounds.height > 300 else { continue }
        return CGRect(x: bounds.minX, y: mainHeight - bounds.maxY,
                      width: bounds.width, height: bounds.height)
    }
    return nil
}

private func companionFrame() -> CGRect {
    let game = balatroFrame()
    let screen = NSScreen.screens.first(where: { screen in
        game.map { screen.frame.intersects($0) } ?? false
    }) ?? NSScreen.main ?? NSScreen.screens[0]
    let usable = screen.visibleFrame
    let height = min(840, max(440, (game?.height ?? usable.height) - 12), usable.height - 12)
    let idealWidth: CGFloat = 430
    if let game = game {
        let room = usable.maxX - game.maxX - 16
        if room >= 300 {
            let width = min(idealWidth, room)
            let x = game.maxX + 8
            let y = min(max(game.maxY - height, usable.minY + 6), usable.maxY - height - 6)
            return CGRect(x: x, y: y, width: width, height: height)
        }
    }
    let width = min(idealWidth, usable.width - 20)
    return CGRect(x: usable.maxX - width - 8, y: usable.maxY - height - 6,
                  width: width, height: height)
}

/// 牌灵图标：深青底、金色圆角描边、金色四角星。与 companion/index.html 里的 SVG 同一造型，纯代码绘制，不含任何游戏素材。
// 像素鬼火图标：17×17 格逐格绘制，外圈一格金色外框，与 companion/index.html 顶部标志同一张图。
let wispPalette: [Character: (CGFloat, CGFloat, CGFloat)] = [
    "B": (0x17, 0x32, 0x2e), // 底板
    "O": (0xe8, 0xbb, 0x60), // 金色外框，与火芯同色
    "K": (0x0c, 0x1f, 0x20), // 眼睛
    "G": (0xe8, 0xbb, 0x60), // 金色火芯
    "T": (0x2f, 0xb5, 0xa0), // 青色外焰
    "L": (0x8f, 0xf0, 0xd8), // 浅青内焰
]
let wispArt = [
    "....T....",
    "...TT....",
    "...TTT...",
    "..TTLTT..",
    ".TTLLTTT.",
    "TTTLGLTTT",
    "TTLGGGLTT",
    "TTGGGGGTT",
    "TTGKGKGTT",
    "TTGKGKGTT",
    ".TTGGGTT.",
    "..TTTTT..",
]
let wispGridSize = 17

func wispGrid() -> [[Character]] {
    let n = wispGridSize
    var grid = [[Character]](repeating: [Character](repeating: ".", count: n), count: n)
    let cut = [2, 1] // 四角按像素切圆
    for y in 0..<n {
        let inset = y < cut.count ? cut[y] : (y > n - 1 - cut.count ? cut[n - 1 - y] : 0)
        for x in inset..<(n - inset) { grid[y][x] = "B" }
    }
    // 底板最外一圈（上下左右任一邻格在底板外）涂成外框。
    let tile = grid
    func outside(_ y: Int, _ x: Int) -> Bool { y < 0 || y >= n || x < 0 || x >= n || tile[y][x] == "." }
    for y in 0..<n {
        for x in 0..<n where tile[y][x] == "B" {
            if outside(y - 1, x) || outside(y + 1, x) || outside(y, x - 1) || outside(y, x + 1) { grid[y][x] = "O" }
        }
    }
    // 尖头细，往下多放一格，视觉上更居中。
    let ox = (n - wispArt[0].count) / 2, oy = 3
    for (y, row) in wispArt.enumerated() {
        for (x, c) in row.enumerated() where c != "." { grid[y + oy][x + ox] = c }
    }
    return grid
}

func cardwispIcon(size: CGFloat = 1024) -> NSImage {
    NSImage(size: NSSize(width: size, height: size), flipped: true) { rect in
        NSGraphicsContext.current?.shouldAntialias = false
        NSGraphicsContext.current?.imageInterpolation = .none
        // 1024 画布上每格 47 点、整张 799 点，与 macOS 图标的标准留白相近，格子边缘不会糊。
        let cell = (rect.width * 47 / 1024).rounded(.down)
        let origin = ((rect.width - cell * CGFloat(wispGridSize)) / 2).rounded(.down)
        for (y, row) in wispGrid().enumerated() {
            for (x, c) in row.enumerated() {
                guard let (r, g, b) = wispPalette[c] else { continue }
                NSColor(srgbRed: r / 255, green: g / 255, blue: b / 255, alpha: 1).setFill()
                NSRect(x: origin + CGFloat(x) * cell, y: origin + CGFloat(y) * cell, width: cell, height: cell).fill()
            }
        }
        return true
    }
}

final class CompanionDelegate: NSObject, NSApplicationDelegate, WKScriptMessageHandler {
    private var window: NSWindow?

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        if message.name == "cardwispClose" { window?.close() }
    }

    private func bringForward() {
        guard let window = window else { return }
        NSApp.activate(ignoringOtherApps: true)
        window.orderFrontRegardless()
        window.makeKey()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let frame = companionFrame()
        let window = NSWindow(contentRect: frame, styleMask: [.titled, .closable, .miniaturizable, .resizable],
                              backing: .buffered, defer: false)
        window.title = "牌灵 · Cardwisp"
        window.minSize = NSSize(width: 300, height: 440)
        window.isReleasedWhenClosed = false
        window.collectionBehavior = [.moveToActiveSpace]
        window.level = .floating
        let configuration = WKWebViewConfiguration()
        configuration.userContentController.add(self, name: "cardwispClose")
        let web = WKWebView(frame: CGRect(origin: .zero, size: frame.size), configuration: configuration)
        web.load(URLRequest(url: URL(string: "http://127.0.0.1:8765/")!))
        window.contentView = web
        self.window = window
        bringForward()
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        bringForward()
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let icon = cardwispIcon()
app.applicationIconImage = icon
// 写到 .app 上，访达和下次启动前的程序坞也显示同一个图标；失败不影响运行。
NSWorkspace.shared.setIcon(icon, forFile: Bundle.main.bundlePath, options: [])
let delegate = CompanionDelegate()
app.delegate = delegate
app.run()
