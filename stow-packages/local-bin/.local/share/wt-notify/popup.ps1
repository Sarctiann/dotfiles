# Popup shown by wt-notify on the monitor where Windows Terminal is, because Windows toasts always appear on
# the primary display. wt-notify prepends $Title, $Body, $Accent, $Seconds, $Sound and $SoundFile (a Windows
# path to a .wav, or empty for Windows' Asterisk sound) before running this.
# Click the popup to dismiss it early. It never takes focus away from the window you're typing in.
$ErrorActionPreference = 'Stop'

Add-Type -ReferencedAssemblies System.Windows.Forms, System.Drawing -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

public static class WtNotifyNative {
    [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr ctx);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr FindWindowEx(IntPtr parent, IntPtr after, string cls, string title);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }

    // Bounds of the other wt-notify popups currently on screen (found by their window title).
    public static List<Rectangle> OpenPopups() {
        List<Rectangle> list = new List<Rectangle>();
        IntPtr h = IntPtr.Zero;
        while ((h = FindWindowEx(IntPtr.Zero, h, null, "wt-notify")) != IntPtr.Zero) {
            RECT r;
            if (IsWindowVisible(h) && GetWindowRect(h, out r))
                list.Add(Rectangle.FromLTRB(r.Left, r.Top, r.Right, r.Bottom));
        }
        return list;
    }
}

public class WtNotifyPopup : Form {
    protected override bool ShowWithoutActivation { get { return true; } }
    protected override CreateParams CreateParams {
        get {
            CreateParams cp = base.CreateParams;
            cp.ExStyle |= 0x00000008 | 0x00000080 | 0x08000000; // TOPMOST | TOOLWINDOW | NOACTIVATE
            return cp;
        }
    }
}
'@

# Per-monitor DPI awareness so coordinates are physical pixels on every monitor (falls back on old Windows).
try { [void][WtNotifyNative]::SetProcessDpiAwarenessContext([IntPtr]-4) } catch { [void][WtNotifyNative]::SetProcessDPIAware() }

# The Windows Terminal window: the foreground one if it's Windows Terminal, else its main window.
$wt = [IntPtr]::Zero
[uint32]$fgPid = 0
$fg = [WtNotifyNative]::GetForegroundWindow()
[void][WtNotifyNative]::GetWindowThreadProcessId($fg, [ref]$fgPid)
if ((Get-Process -Id $fgPid -ErrorAction SilentlyContinue).ProcessName -eq 'WindowsTerminal') {
    $wt = $fg
} else {
    $proc = Get-Process WindowsTerminal -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } | Select-Object -First 1
    if ($proc) { $wt = $proc.MainWindowHandle }
}

# Screen.FromHandle uses the restored position when the window is minimized.
if ($wt -ne [IntPtr]::Zero) { $screen = [System.Windows.Forms.Screen]::FromHandle($wt) }
else { $screen = [System.Windows.Forms.Screen]::PrimaryScreen }

$dpi = 96
if ($wt -ne [IntPtr]::Zero) { try { $d = [WtNotifyNative]::GetDpiForWindow($wt); if ($d -gt 0) { $dpi = $d } } catch {} }
$s = $dpi / 96.0
function Px([double]$v) { [int][Math]::Round($v * $s) }

$bg = [System.Drawing.Color]::FromArgb(32, 32, 32)
$accentColor = [System.Drawing.ColorTranslator]::FromHtml($Accent)
$titleFont = New-Object System.Drawing.Font('Segoe UI Semibold', (Px 15), [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
$bodyFont = New-Object System.Drawing.Font('Segoe UI', (Px 13), [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)

$width = Px 380
$pad = Px 14
$bar = Px 12     # left border, wider than the rest
$border = Px 2   # top, right and bottom borders
$textWidth = $width - $bar - $border - 2 * $pad
$flags = [System.Windows.Forms.TextFormatFlags]::WordBreak
function TextH($text, $font, $w = $textWidth) { [System.Windows.Forms.TextRenderer]::MeasureText($text, $font, (New-Object System.Drawing.Size($w, 0)), $flags).Height }
$titleLineH = TextH 'Ag' $titleFont
$bodyLineH = TextH 'Ag' $bodyFont
# Time the popup appeared, right-aligned on the title's first line; the title wraps in the space left of it.
$timeText = Get-Date -Format 'HH:mm:ss'
$timeW = [System.Windows.Forms.TextRenderer]::MeasureText($timeText, $bodyFont).Width
$titleWidth = $textWidth - $timeW - (Px 8)
# Title up to 2 lines and body up to 3 (cut with "…"), so long messages don't make huge popups.
$titleH = [Math]::Min((TextH $Title $titleFont $titleWidth), 2 * $titleLineH)
$bodyH = 0
$gap = 0
if ($Body) {
    $bodyH = [Math]::Min((TextH $Body $bodyFont), 3 * $bodyLineH)
    $gap = Px 4
}
$innerH = $pad + $titleH + $gap + $bodyH + $pad
$height = $innerH + 2 * $border

$form = New-Object WtNotifyPopup
$form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::None
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$form.ShowInTaskbar = $false
$form.TopMost = $true
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
$form.BackColor = $accentColor  # shows through as the border around $inner
$form.Text = 'wt-notify'
$form.Size = New-Object System.Drawing.Size($width, $height)
$area = $screen.WorkingArea
$margin = Px 16
$x = $area.Right - $width - $margin

# Stacking: the first popup sits with its center at 1/4 of the screen height from the bottom; popups on screen
# at the same time stack upwards, $spacing apart, each one taking the lowest free spot. The placement lock is
# held until this popup is visible, so two popups fired at the same instant can't pick the same spot.
$spacing = Px 6
$placeLock = New-Object System.Threading.Mutex($false, 'Local\wt-notify-place')
try { $locked = $placeLock.WaitOne(3000) } catch [System.Threading.AbandonedMutexException] { $locked = $true }
$busy = @([WtNotifyNative]::OpenPopups() | Where-Object { $_.Left -lt ($x + $width) -and $_.Right -gt $x })
$base = $area.Bottom - [int]($area.Height / 4) - [int]($height / 2)
$candidates = @($base)
foreach ($b in $busy) { $candidates += ($b.Top - $spacing - $height) }
$free = @($candidates | Where-Object {
    $cy = $_
    $cy -le $base -and $cy -ge $area.Top -and
        -not ($busy | Where-Object { $cy -lt ($_.Bottom + $spacing) -and ($cy + $height + $spacing) -gt $_.Top })
} | Sort-Object -Descending)
$y = $base
if ($free.Count) { $y = $free[0] }
$form.Location = New-Object System.Drawing.Point($x, $y)

$inner = New-Object System.Windows.Forms.Panel
$inner.BackColor = $bg
$inner.SetBounds($bar, $border, ($width - $bar - $border), $innerH)

$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = $Title
$titleLabel.Font = $titleFont
$titleLabel.ForeColor = [System.Drawing.Color]::White
$titleLabel.SetBounds($pad, $pad, $titleWidth, $titleH)
$titleLabel.UseMnemonic = $false
$titleLabel.AutoEllipsis = $true

# Bottom-aligned with the title's first line, so both share the baseline.
$timeLabel = New-Object System.Windows.Forms.Label
$timeLabel.Text = $timeText
$timeLabel.Font = $bodyFont
$timeLabel.ForeColor = [System.Drawing.Color]::FromArgb(150, 150, 150)
$timeLabel.TextAlign = [System.Drawing.ContentAlignment]::TopRight
$timeLabel.SetBounds(($pad + $textWidth - $timeW), ($pad + $titleLineH - $bodyLineH), $timeW, $bodyLineH)

$bodyLabel = New-Object System.Windows.Forms.Label
$bodyLabel.Text = $Body
$bodyLabel.Font = $bodyFont
$bodyLabel.ForeColor = [System.Drawing.Color]::FromArgb(205, 205, 205)
$bodyLabel.SetBounds($pad, ($pad + $titleH + $gap), $textWidth, $bodyH)
$bodyLabel.UseMnemonic = $false
$bodyLabel.AutoEllipsis = $true

$inner.Controls.AddRange(@($titleLabel, $timeLabel, $bodyLabel))
$form.Controls.Add($inner)
foreach ($c in @($form, $inner, $titleLabel, $timeLabel, $bodyLabel)) { $c.Add_Click({ $form.Close() }) }

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = [Math]::Max(1, $Seconds) * 1000
$timer.Add_Tick({ $timer.Stop(); $form.Close() })
$form.Add_Shown({
    $timer.Start()
    if ($locked) { $placeLock.ReleaseMutex() }
})

if ($Sound) {
    try { (New-Object System.Media.SoundPlayer $SoundFile).Play() }
    catch { [System.Media.SystemSounds]::Asterisk.Play() }
}
[System.Windows.Forms.Application]::Run($form)
