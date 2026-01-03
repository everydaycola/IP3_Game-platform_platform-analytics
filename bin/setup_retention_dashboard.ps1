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

  # Python helper that builds the player-sessions-* index used by
  # the "Avg Session Duration (min)" KPI in the engagement dashboard.
  [string]$SessionBuilderScript = ".\scripts\build_player_sessions_index.py",

  # Python script that generates retention events into platform-events-*
  [string]$RetentionDataGenerator = ".\scripts\generate_retention_data.py",

  # Updated platform-events index template (ensures player_id.keyword exists)
  [string]$PlatformEventsTemplateFile = ".\elasticsearch\templates\platform-events-template.json",

  [bool]$Recreate = $true,
  [bool]$GenerateRetentionData = $true,  # Auto-generate retention data for dashboard
  [bool]$CleanData = $false  # Delete all platform-events data before regenerating (forces fresh cohorts)
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

function EsPostJson($path, $jsonBody) {
  Invoke-RestMethod -Method POST -Uri "$ElasticUrl$path" -Headers ($esAuth + @{ "Content-Type"="application/json" }) -Body $jsonBody
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
foreach ($f in @($TfPlayerFirstSeenFile,$TfRetentionCohortFile,$EnrichPolicyFile,$PipelineFile,$KibanaExportFile,$SessionBuilderScript,$PlatformEventsTemplateFile,$RetentionDataGenerator)) {
  if (-not (Test-Path $f)) { throw "Missing file: $f" }
}

# Clean existing data if requested (forces fresh cohort generation)
if ($CleanData) {
  Log "0) Clean existing data (platform-events and player-sessions)"
  try {
    # Delete platform-events indices
    try {
      $indices = Invoke-RestMethod -Method GET -Uri "$ElasticUrl/_cat/indices/platform-events-*?h=index" -Headers $esAuth -ErrorAction SilentlyContinue
      if ($indices) {
        $indexList = $indices -split "`n" | Where-Object { $_ -match "platform-events-" }
        foreach ($index in $indexList) {
          $index = $index.Trim()
          if ($index) {
            Log "   Deleting index: $index"
            EsDelete "/$index" | Out-Null
          }
        }
      }
    } catch {
      Write-Host "   Note: Could not delete platform-events indices (may not exist)" -ForegroundColor DarkGray
    }

    # Delete player-sessions indices
    try {
      $indices = Invoke-RestMethod -Method GET -Uri "$ElasticUrl/_cat/indices/player-sessions-*?h=index" -Headers $esAuth -ErrorAction SilentlyContinue
      if ($indices) {
        $indexList = $indices -split "`n" | Where-Object { $_ -match "player-sessions-" }
        foreach ($index in $indexList) {
          $index = $index.Trim()
          if ($index) {
            Log "   Deleting index: $index"
            EsDelete "/$index" | Out-Null
          }
        }
      }
    } catch {
      Write-Host "   Note: Could not delete player-sessions indices (may not exist)" -ForegroundColor DarkGray
    }

    Log "   Data cleaned - will regenerate fresh retention data"
  } catch {
    Write-Host "   Failed to clean data (continuing anyway)" -ForegroundColor Yellow
  }
}

# Generate retention data if requested (before transforms/enrichment)
if ($GenerateRetentionData) {
  Log "1) Generate retention data for dashboard"
  try {
    # Check if platform-events-* already has session_started events with player_id
    $existingSessionCount = 0
    try {
      $countBody = '{"query":{"bool":{"must":[{"term":{"event_type":"session_started"}},{"exists":{"field":"player_id"}}]}}}'
      $countResp = Invoke-RestMethod -Method POST -Uri "$ElasticUrl/platform-events-*/_count" -Headers ($esAuth + @{ "Content-Type"="application/json" }) -Body $countBody -ErrorAction SilentlyContinue
      $existingSessionCount = $countResp.count
    } catch {
      # Index might not exist yet; that's fine
    }

    if ($existingSessionCount -gt 100 -and -not $CleanData) {
      Log "   Retention data already exists ($existingSessionCount session events) - skipping generation"
    } else {
      Log "   Generating retention data (medium dataset: 60 days, ~30 users/day)..."
      Log "   This ensures dashboard cohorts on D1/D7/D30 dates and takes ~30 seconds"
      
      # Run retention generator in auto mode (non-interactive)
      $env:PYTHONUNBUFFERED = "1"
      python $RetentionDataGenerator --auto
      
      Log "   Waiting 30 seconds for Logstash to process retention events..."
      Start-Sleep -Seconds 30
    }
  } catch {
    Write-Host "   Failed to generate retention data (continuing anyway)" -ForegroundColor Yellow
    Write-Host "   Error: $_" -ForegroundColor Yellow
  }
}
 
Log "2) Ensure platform-events index has player_id.keyword mapping"
try {
  # Upload the latest index template from the repo (host filesystem).
  Log "   PUT _index_template/platform-events from $PlatformEventsTemplateFile"
  EsPutJsonFile "/_index_template/platform-events" $PlatformEventsTemplateFile | Out-Null

  # Resolve the concrete index behind the 'platform-events' alias.
  $aliasResp = Invoke-RestMethod -Method GET -Uri "$ElasticUrl/_alias/platform-events" -Headers $esAuth -ErrorAction Stop
  $sourceIndexName = ($aliasResp.PSObject.Properties.Name | Select-Object -First 1)

  # Inspect mapping to see if player_id.keyword already exists.
  $mapping = Invoke-RestMethod -Method GET -Uri "$ElasticUrl/$sourceIndexName/_mapping" -Headers $esAuth -ErrorAction Stop
  # Index names contain dashes, so access via dynamic property expression
  $indexMapping = $mapping.$($sourceIndexName)
  $playerMapping = $indexMapping.mappings.properties.player_id
  
  if (-not $playerMapping -or -not $playerMapping.fields -or -not $playerMapping.fields.keyword) {
    Log "   Adding player_id + player_id.keyword mapping to $sourceIndexName"
    $mappingBody = '{"properties":{"player_id":{"type":"text","fields":{"keyword":{"type":"keyword","ignore_above":256}}}}}'
    EsPostJson "/$sourceIndexName/_mapping" $mappingBody | Out-Null
  } else {
    Log "   player_id.keyword already present - no mapping update needed"
  }
} catch {
  Write-Host "   ⚠️  Failed to verify/fix platform-events mapping (continuing)" -ForegroundColor Yellow
}

Log "3) Create player_first_seen transform"
StopDeleteTransform $TfPlayerFirstSeenId
if (-not (EsExists "/_transform/$TfPlayerFirstSeenId")) {
  Log " PUT _transform/$TfPlayerFirstSeenId"
  EsPutJsonFile "/_transform/$TfPlayerFirstSeenId" $TfPlayerFirstSeenFile | Out-Null
}

Log "4) Start player_first_seen"
try { EsPost "/_transform/$TfPlayerFirstSeenId/_start" | Out-Null } catch {}

Log "Waiting for player_first_seen to index data..."
for ($i=0; $i -lt 30; $i++) {
  $stats = Invoke-RestMethod -Uri "$ElasticUrl/_transform/$TfPlayerFirstSeenId/_stats" -Headers $esAuth
  if ($stats.transforms[0].stats.documents_indexed -gt 0) { break }
  Start-Sleep 2
}

Log "5) Enrich policy create + execute"

# Only create the enrich policy if it does not already exist. Note that
# GET _enrich/policy/{name} always returns 200 with an empty policies[]
# array when the policy is missing, so we must inspect the response
# rather than relying on HTTP status.
try {
  $policyResp = Invoke-RestMethod -Method GET -Uri "$ElasticUrl/_enrich/policy/$EnrichPolicyName" -Headers $esAuth -ErrorAction SilentlyContinue
} catch {
  $policyResp = $null
}

$policyExists = $false
if ($policyResp -and $policyResp.policies -and $policyResp.policies.Count -gt 0) {
  $policyExists = $true
}

if (-not $policyExists) {
  Log "   Creating enrich policy $EnrichPolicyName from $EnrichPolicyFile"
  EsPutJsonFile "/_enrich/policy/$EnrichPolicyName" $EnrichPolicyFile | Out-Null
} else {
  Log "   Enrich policy $EnrichPolicyName already exists - reusing"
}

Log "   Executing enrich policy $EnrichPolicyName"
try {
  EsPost "/_enrich/policy/$EnrichPolicyName/_execute" | Out-Null
} catch {
  Write-Host "   ⚠️  Failed to execute enrich policy $EnrichPolicyName (continuing)" -ForegroundColor Yellow
}

Log "6) Ingest pipeline PUT _ingest/pipeline/$PipelineName"
EsPutJsonFile "/_ingest/pipeline/$PipelineName" $PipelineFile | Out-Null

Log "7) Create enriched events index (events-enriched-03) via reindex + ingest pipeline"
try {
  # If Recreate is true and the index already exists, drop it so we always
  # rebuild from the latest platform-events-* data.
  if ($Recreate -and (EsExists "/events-enriched-03/_count")) {
    Log "   Deleting existing events-enriched-03 index (Recreate=$Recreate)"
    EsDelete "/events-enriched-03" | Out-Null
  }

  $enrichedBody = @{
    source = @{ index = "platform-events-*" }
    dest   = @{ index = "events-enriched-03"; pipeline = $PipelineName }
  } | ConvertTo-Json -Depth 4

  Log "   POST _reindex -> events-enriched-03 (from platform-events-*)"
  EsPostJson "/_reindex?wait_for_completion=true&refresh=true" $enrichedBody | Out-Null

  # Safety net: if for some reason the reindex didn't create the index,
  # make sure it exists so the transform validation can pass.
  if (-not (EsExists "/events-enriched-03/_count")) {
    Log "   events-enriched-03 still missing after reindex, creating empty index"
    Invoke-RestMethod -Method PUT -Uri "$ElasticUrl/events-enriched-03" -Headers ($esAuth + @{ "Content-Type"="application/json" }) -Body "{}" | Out-Null
  }
} catch {
  Write-Host "   ⚠️  Failed to build events-enriched-03 (continuing)" -ForegroundColor Yellow
  # As a fallback, ensure the index exists (even if empty) so the
  # retention_cohort transform can still be created.
  try {
    if (-not (EsExists "/events-enriched-03/_count")) {
      Invoke-RestMethod -Method PUT -Uri "$ElasticUrl/events-enriched-03" -Headers ($esAuth + @{ "Content-Type"="application/json" }) -Body "{}" | Out-Null
    }
  } catch {}
}

Log "8) Create + start retention_cohort transform"
StopDeleteTransform $TfRetentionCohortId
 
# (Re)create destination index for retention_cohort with correct mappings so
# cohort_date is a date field and retention metrics are numeric.
try {
  if ($Recreate -and (EsExists "/retention_cohort/_count")) {
    Log "   Deleting existing retention_cohort index (Recreate=$Recreate)"
    EsDelete "/retention_cohort" | Out-Null
  }

  if (-not (EsExists "/retention_cohort/_count")) {
    Log "   Creating retention_cohort index with explicit mappings"
    $retentionIndexBody = '{"mappings":{"properties":{' +
      '"cohort_date":{"type":"date"},' +
      '"cohort_size":{"properties":{"players":{"type":"long"}}},' +
      '"d1_retained":{"properties":{"players":{"type":"long"}}},' +
      '"d7_retained":{"properties":{"players":{"type":"long"}}},' +
      '"d30_retained":{"properties":{"players":{"type":"long"}}},' +
      '"d1_retention":{"type":"double"},' +
      '"d7_retention":{"type":"double"},' +
      '"d30_retention":{"type":"double"}' +
    '}}}'
    Invoke-RestMethod -Method PUT -Uri "$ElasticUrl/retention_cohort" -Headers ($esAuth + @{ "Content-Type"="application/json" }) -Body $retentionIndexBody | Out-Null
  }
} catch {
  Write-Host "   ⚠️  Failed to (re)create retention_cohort index with mappings (continuing)" -ForegroundColor Yellow
}

if (-not (EsExists "/_transform/$TfRetentionCohortId")) {
  Log " PUT _transform/$TfRetentionCohortId"
  EsPutJsonFile "/_transform/$TfRetentionCohortId" $TfRetentionCohortFile | Out-Null
}
try { EsPost "/_transform/$TfRetentionCohortId/_start" | Out-Null } catch {}

Log "9) Build player-sessions index for Avg Session Duration KPI"
try {
  # Use the Python script which sessionizes platform-events-* into
  # player-sessions-* with session_duration_minutes.
  python $SessionBuilderScript
} catch {
  Write-Host "   ⚠️  Failed to build player-sessions index (continuing anyway)" -ForegroundColor Yellow
}


Log "10) Skip Kibana .ndjson import (dashboard will be created via Python script)"
Write-Host "   Note: The User Engagement & Retention dashboard will be created by" -ForegroundColor Gray
Write-Host "   scripts/create_retention_engagement_dashboard.py with the latest KPI definitions" -ForegroundColor Gray

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
