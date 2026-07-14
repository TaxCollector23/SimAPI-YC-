class Simapi < Formula
  desc "Validate simulation results before they reach production"
  homepage "https://sim-api.vercel.app"
  head "https://github.com/TaxCollector23/SimAPI-YC-.git", branch: "main"
  license "MIT"

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
