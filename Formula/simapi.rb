class Simapi < Formula
  desc "Validate simulation results before they reach production"
  homepage "https://sim-api.vercel.app"
  url "https://github.com/TaxCollector23/SimAPI-YC-/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "7473721cb0e9a85a2eca34bb2b5d781ad59ef5bd69794cd9e590f6f6339dde3d"
  license "MIT"
  head "https://github.com/TaxCollector23/SimAPI-YC-.git", branch: "main"

  depends_on "node"

  def install
    libexec.install "sdk-node/bin/simapi.js"
    (bin/"simapi").write <<~SH
      #!/bin/sh
      exec node "#{libexec}/simapi.js" "$@"
    SH
    chmod 0755, bin/"simapi"
  end

  test do
    assert_match "v1.0.0", shell_output("#{bin}/simapi version")
  end
end
