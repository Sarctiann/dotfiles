param(
    [string]$Title = "OpenCode",
    [string]$Message = "OpenCode notification"
)

$ErrorActionPreference = "Stop"

[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
    [Windows.UI.Notifications.ToastTemplateType]::ToastText02
)
$textNodes = $template.GetElementsByTagName("text")
$textNodes.Item(0).AppendChild($template.CreateTextNode($Title)) | Out-Null
$textNodes.Item(1).AppendChild($template.CreateTextNode($Message)) | Out-Null

$audio = $template.CreateElement("audio")
$audio.SetAttribute("src", "ms-winsoundevent:Notification.Default")
$template.DocumentElement.AppendChild($audio) | Out-Null

$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
$appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
