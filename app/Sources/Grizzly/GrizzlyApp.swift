#if !os(macOS)
@main
enum GrizzlyStub {
    static func main() {
        print("Grizzly.app runs on macOS. GrizzlyCore builds and tests on any platform.")
    }
}
#endif
