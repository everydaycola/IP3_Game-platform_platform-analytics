Param(
  [string]$ElasticUrl = $env:ELASTIC_URL,
  [string]$KibanaUrl  = $env:KIBANA_URL,
  [string]$ElasticUser = $env:ELASTIC_USER,
  [string]$ElasticPass = $env:ELASTIC_PASS,
  [string]$KibanaUser  = $env:KIBANA_USER,
  [string]$KibanaPass  = $env:KIBANA_PASS,

  [string]$KibanaExportFile = ".\kibana\exports\user_engagement_retention.ndjson",

  [string]$TfPlayerFirstSeenId = "player_first_seen",
  [string]$TfPlayerFirstSeenFile = ".\elasticsearch\transforms\player_first_seen.json",

  [string]$TfRetentionCohortId = "retention_cohort",
  [string]$TfRetentionCohortFile = ".\elasticsearch\transforms\retention_cohort.json",

  [string]$EnrichPolicyName = "player_first_seen_enrich_policy",
  [string]$EnrichPolicyFile = ".\elasticsearch\enrich\player_first_seen_enrich_policy.json",

  [string]$PipelineName = "player_cohort_enrich",
  [string]$PipelineFile = ".\elasticsearch\ingest_pipelines\player_cohort_enrich.json",

  [bool]$Recreate = $true
)

if ([string]::IsNullOrWhiteSpace($ElasticUrl)) { $ElasticUrl = "http://localhost:9200" }
if ([string]::IsNullOrWhiteSpace($KibanaUrl))  { $KibanaUrl  = "http://localhost:5601" }
if ([string]::IsNullOrWhiteSpace($ElasticUser)) { $ElasticUser = "elastic" }
if ([string]::IsNullOrWhiteSpace($ElasticPass)) { $ElasticPass = "changeme" }
if ([string]::IsNullOrWhiteSpace($KibanaUser))  { $KibanaUser  = "elastic" }
if ([string]::IsNullOrWhiteSpace($KibanaPass))  { $KibanaPass  = "changeme" }

function Log($msg) { Write-Host "`n==> $msg" }

function AuthHeader($user, $pass) {
  $bytes = [System.Text.Encoding]::UTF8.GetBytes("$user`:$pass")
  $b64 = [Convert]::ToBase64String($bytes)
  return @{ Authorization = "Basic $b64" }
}

$esAuth = AuthHeader $ElasticUser $ElasticPass

function EsExists($path) {
  try {
    Invoke-WebRequest -Method GET -Uri "$ElasticUrl$path" -Headers $esAuth -UseBasicParsing -ErrorAction Stop | Out-Null
    return $true
  } catch { return $false }
}

function EsPutJsonFile($path, $file) {
  # -Encoding utf8 avoids surprises with BOM / special chars
  $body = Get-Content $file -Raw -Encoding utf8
  Invoke-RestMethod -Method PUT -Uri "$ElasticUrl$path" -Headers ($esAuth + @{ "Content-Type"="application/json" }) -Body $body
}

function EsPost($path) {
  Invoke-RestMethod -Method POST -Uri "$ElasticUrl$path" -Headers $esAuth
}

function EsDelete($path) {
  Invoke-RestMethod -Method DELETE -Uri "$ElasticUrl$path" -Headers $esAuth
}

function StopDeleteTransform($id) {
  if (EsExists "/_transform/$id") {
    Log "Transform exists: $id"
    if ($Recreate) {
      Log " stopping $id ..."
      try { EsPost "/_transform/$id/_stop?force=true" | Out-Null } catch {}
      Log " deleting $id ..."
      try { EsDelete "/_transform/$id?force=true" | Out-Null } catch {}
    }
  }
}

# Prechecks
Log "Prechecks"
foreach ($f in @($TfPlayerFirstSeenFile,$TfRetentionCohortFile,$EnrichPolicyFile,$PipelineFile,$KibanaExportFile)) {
  if (-not (Test-Path $f)) { throw "Missing file: $f" }
}

Log "Waiting for events-enriched-* to exist..."
while (-not (EsExists "/events-enriched-*/_count")) {
  Start-Sleep -Seconds 5
}


Log "2) Transforms create"
StopDeleteTransform $TfPlayerFirstSeenId
if (-not (EsExists "/_transform/$TfPlayerFirstSeenId")) {
  Log " PUT _transform/$TfPlayerFirstSeenId"
  EsPutJsonFile "/_transform/$TfPlayerFirstSeenId" $TfPlayerFirstSeenFile | Out-Null
}

# StopDeleteTransform $TfRetentionCohortId
# if (-not (EsExists "/_transform/$TfRetentionCohortId")) {
#   Log " PUT _transform/$TfRetentionCohortId"
#   EsPutJsonFile "/_transform/$TfRetentionCohortId" $TfRetentionCohortFile | Out-Null
# }

Log "3) Start player_first_seen"
try { EsPost "/_transform/$TfPlayerFirstSeenId/_start" | Out-Null } catch {}

Log "Waiting for player_first_seen to index data..."
for ($i=0; $i -lt 30; $i++) {
  $stats = Invoke-RestMethod -Uri "$ElasticUrl/_transform/$TfPlayerFirstSeenId/_stats" -Headers $esAuth
  if ($stats.transforms[0].stats.documents_indexed -gt 0) { break }
  Start-Sleep 2
}

Log "4) Enrich policy create + execute"
EsPutJsonFile "/_enrich/policy/$EnrichPolicyName" $EnrichPolicyFile | Out-Null
EsPost "/_enrich/policy/$EnrichPolicyName/_execute" | Out-Null

Log "5) Ingest pipeline PUT _ingest/pipeline/$PipelineName"
EsPutJsonFile "/_ingest/pipeline/$PipelineName" $PipelineFile | Out-Null


Log "7) Kibana import .ndjson (overwrite=true)"
# Windows PowerShell 5.1 doesn't support Invoke-WebRequest -Form. Use curl.exe for multipart upload.
$importUrl = "$KibanaUrl/api/saved_objects/_import?overwrite=true"
$curl = Get-Command curl.exe -ErrorAction SilentlyContinue
if (-not $curl) { throw "curl.exe not found on PATH. Install curl or use PowerShell 7+." }

# Use -f to fail on HTTP errors, -sS for readable output.
& $curl.Source -f -sS -u "$KibanaUser`:$KibanaPass" -H "kbn-xsrf: true" -F "file=@$KibanaExportFile" $importUrl | Out-Null

Log "DONE ✅"

Write-Host ""
Write-Host "==> Post-deploy checks (what to verify) " -ForegroundColor Cyan
Write-Host ""

# URLs (Kibana)
$kibanaBase = "http://localhost:5601"
Write-Host "Open Kibana:            $kibanaBase"
Write-Host "Dashboards list:        $kibanaBase/app/dashboards#/list"
Write-Host "Dev Tools (Console):    $kibanaBase/app/dev_tools#/console"
Write-Host ""

Write-Host "How to verify the dashboard exists:" -ForegroundColor Yellow
Write-Host "  1) Go to Dashboards list"
Write-Host "  2) Search for:  User Engagement & Retention"
Write-Host "  3) Open it and confirm panels load (DAU/WAU/MAU + Retention section)"
Write-Host ""

Write-Host "How to verify backend assets (copy/paste into Dev Tools):" -ForegroundColor Yellow
Write-Host "  GET _transform/player_first_seen/_stats"
Write-Host "  GET _transform/retention_cohort/_stats"
Write-Host "  GET _enrich/policy/player_first_seen_enrich_policy"
Write-Host "  GET _ingest/pipeline/player_cohort_enrich"
Write-Host "  GET retention_cohort/_count"
Write-Host ""

Write-Host "Expected results:" -ForegroundColor Yellow
Write-Host "  - both transforms state: started"
Write-Host "  - ingest pipeline exists"
Write-Host "  - retention_cohort index has documents"
Write-Host ""
Write-Host "Credentials reminder: elastic / changeme" -ForegroundColor DarkGray
Write-Host ""
