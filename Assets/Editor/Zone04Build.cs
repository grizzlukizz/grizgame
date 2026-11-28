using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;

namespace Zone04.Editor
{
    public static class Zone04Build
    {
        [MenuItem("Zone 04/Build Windows x64")]
        public static void Windows()
        {
            Directory.CreateDirectory("Builds/Windows");
            BuildReport report = BuildPipeline.BuildPlayer(
                new[] { "Assets/Scenes/Quarantine.unity" },
                "Builds/Windows/Zone04.exe",
                BuildTarget.StandaloneWindows64,
                BuildOptions.None);
            if (report.summary.result != BuildResult.Succeeded)
                throw new InvalidOperationException("Build failed: " + report.summary.result);
        }
    }
}
