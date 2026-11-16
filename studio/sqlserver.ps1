# Windows-authentication-only, selected-database read-only adapter. Request JSON
# arrives on stdin; no credentials/connection string is written to disk or argv.
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding=New-Object System.Text.UTF8Encoding($false)
$request=[Console]::In.ReadToEnd()|ConvertFrom-Json
Add-Type -AssemblyName System.Data
$builder=New-Object System.Data.SqlClient.SqlConnectionStringBuilder
$builder['Data Source']=[string]$request.server
$builder['Initial Catalog']=[string]$request.database
$builder['Integrated Security']=$true
$builder['Encrypt']=[bool]$request.encrypt
$builder['TrustServerCertificate']=[bool]$request.trust_server_certificate
$builder['Connect Timeout']=10
$builder['Application Name']='Free Bible Reader read-only importer'
$builder['ApplicationIntent']='ReadOnly'
$connection=New-Object System.Data.SqlClient.SqlConnection($builder.ConnectionString)
function Query-Rows([string]$sql) {
    $cmd=$connection.CreateCommand();$cmd.CommandText=$sql;$cmd.CommandTimeout=30
    $reader=$cmd.ExecuteReader()
    try {
        while($reader.Read()) {
            $row=[ordered]@{}
            for($i=0;$i -lt $reader.FieldCount;$i++) { $v=$reader.GetValue($i);if($v -is [DBNull]){$v=$null};if($v -is [Guid]){$v=$v.ToString()};$row[$reader.GetName($i)]=$v }
            [pscustomobject]$row
        }
    } finally {$reader.Close();$cmd.Dispose()}
}
function Quote-Name([string]$value) {
    if($value.Length -lt 1 -or $value.Length -gt 128 -or $value -match '[\x00-\x1f]'){throw 'INVALID_IDENTIFIER'}
    return '['+$value.Replace(']',']]')+']'
}
try {
    $connection.Open()
    if($request.action -eq 'inspect') {
        $tables=@(Query-Rows 'SELECT TABLE_SCHEMA AS schema_name,TABLE_NAME AS table_name FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE=''BASE TABLE'' ORDER BY TABLE_SCHEMA,TABLE_NAME')
        $columns=@(Query-Rows 'SELECT TABLE_SCHEMA AS schema_name,TABLE_NAME AS table_name,COLUMN_NAME AS column_name,DATA_TYPE AS data_type,ORDINAL_POSITION AS ordinal FROM INFORMATION_SCHEMA.COLUMNS ORDER BY TABLE_SCHEMA,TABLE_NAME,ORDINAL_POSITION')
        @{status='CONNECTED';authentication='Windows integrated';tables=$tables;columns=$columns;read_only_intent=$true}|ConvertTo-Json -Depth 8 -Compress
    } elseif($request.action -eq 'corpus-editions') {
        # Known relational corpus profile: identifiers are native metadata, not
        # guessed translation/versification equivalence. This remains SELECT only.
        $rows=@(Query-Rows 'SELECT e.SourceVersionKey AS source_edition_id,e.EditionName AS name,CONVERT(nvarchar(36),r.RevisionId) AS revision_id,l.SourceLabel AS language,l.EnglishLabel AS language_english,r.ExpectedUnits AS source_record_count,r.ValidationStatus AS validation_status FROM corpus.BibleEdition e JOIN corpus.EditionRevision r ON r.EditionId=e.EditionId LEFT JOIN corpus.Language l ON l.LanguageId=e.LanguageId ORDER BY e.SourceVersionKey')
        @{editions=$rows;source_identifiers_are_actual=$true;coverage_policy='Metadata expected count, not a fresh full-table validation'}|ConvertTo-Json -Depth 8 -Compress
    } elseif($request.action -eq 'rows') {
        $table=(Quote-Name $request.schema)+'.'+(Quote-Name $request.table)
        $cmd=$connection.CreateCommand();$cmd.CommandTimeout=60
        $sql='SELECT TOP (@maximum) * FROM '+$table
        [void]$cmd.Parameters.Add('@maximum',[System.Data.SqlDbType]::Int);$cmd.Parameters['@maximum'].Value=[int]$request.maximum
        if($request.profile -eq 'biblia-corpus-lab') {
            $sql='SELECT TOP (@maximum) t.SourceRecordId AS source_record_id,b.SourceBookLabel AS book,c.SourceChapterLabel AS chapter,t.StartVerseLabel AS verse,t.EndVerseLabel AS end_verse,t.OriginalText AS text,CONVERT(nvarchar(36),t.UnitGuid) AS source_unit_guid,CONVERT(nvarchar(36),t.RevisionId) AS source_revision_id FROM corpus.TextUnit t JOIN corpus.Chapter c ON c.ChapterId=t.ChapterId AND c.RevisionId=t.RevisionId JOIN corpus.EditionBook b ON b.EditionBookId=c.EditionBookId AND b.RevisionId=c.RevisionId WHERE t.RevisionId=@edition ORDER BY t.SourceRecordId'
            [void]$cmd.Parameters.Add('@edition',[System.Data.SqlDbType]::UniqueIdentifier);$cmd.Parameters['@edition'].Value=[Guid]$request.edition_value
        } elseif($request.edition_column) {
            $sql+=' WHERE '+(Quote-Name $request.edition_column)+'=@edition'
            [void]$cmd.Parameters.Add('@edition',[System.Data.SqlDbType]::NVarChar,4000);$cmd.Parameters['@edition'].Value=[string]$request.edition_value
        }
        # A stable unique source record key must be selected by the user.
        if($request.profile -ne 'biblia-corpus-lab'){$sql+=' ORDER BY '+(Quote-Name $request.order_column)};$cmd.CommandText=$sql
        $reader=$cmd.ExecuteReader()
        try {
            while($reader.Read()) {
                $row=[ordered]@{}
                for($i=0;$i -lt $reader.FieldCount;$i++) {$v=$reader.GetValue($i);if($v -is [DBNull]){$v=$null};if($v -is [Guid]){$v=$v.ToString()};if(($v -is [string] -and $v.Length -gt 1000000) -or ($v -is [byte[]] -and $v.Length -gt 1000000)){throw 'SQLSERVER_CELL_LIMIT'};if($v -is [byte[]]){$v=[Convert]::ToBase64String($v)};$row[$reader.GetName($i)]=$v}
                [pscustomobject]$row|ConvertTo-Json -Depth 8 -Compress
            }
        } finally {$reader.Close();$cmd.Dispose()}
    } else {throw 'INVALID_SQLSERVER_ACTION'}
} catch {
    # Provider diagnostics can contain server names; emit only a bounded code.
    [Console]::Error.WriteLine('SQLSERVER_READ_ONLY_OPERATION_FAILED: '+$_.Exception.GetType().Name)
    exit 2
} finally {$connection.Dispose()}
