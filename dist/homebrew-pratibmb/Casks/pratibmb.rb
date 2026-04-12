cask "pratibmb" do
  version "0.2.0"

  on_arm do
    url "https://github.com/tapaskar/Pratibmb/releases/download/v#{version}/Pratibmb_#{version}_aarch64.dmg"
    sha256 :no_check
  end

  on_intel do
    url "https://github.com/tapaskar/Pratibmb/releases/download/v#{version}/Pratibmb_#{version}_x64.dmg"
    sha256 :no_check
  end

  name "Pratibmb"
  desc "Chat with your 10-years-younger self. 100% local, no cloud, no telemetry"
  homepage "https://pratibmb.com"

  depends_on formula: "python@3.11"

  app "Pratibmb.app"

  caveats <<~EOS
    Pratibmb requires Python 3.9+ and ~8GB RAM for the full pipeline.

    Install the Python backend (required on first run):
      pip install pratibmb --prefer-binary \
        --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

    On first launch, Pratibmb downloads ~2.5GB of AI models.
    After that, it works fully offline — no internet required.

    Optional fine-tuning (Apple Silicon):
      pip install mlx-lm
  EOS
end
