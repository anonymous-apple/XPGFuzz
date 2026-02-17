## Bftpd (FTP) Protocol Notes

This document provides **protocol-level** notes for fuzzing Bftpd via FTP control/data channels.
It is intentionally written as a compact “knowledge base” entry to support retrieval (RAG) and
seed enrichment. It focuses on **commands, session states, reply codes, and data-connection
semantics** commonly exercised by FTP servers like Bftpd.

> Note: FTP is standardized (e.g., RFC 959 + later extensions). Individual servers vary in
> supported commands/extensions and exact reply texts. For fuzzing, **codes + state transitions**
> and **parsing behavior** matter more than exact wording.

---

## 1) Channels & framing

- **Control channel**: TCP, text line protocol.
  - Client sends commands as ASCII lines terminated by **CRLF**: `COMMAND[ SP arg] CRLF`
  - Server replies with numeric **3-digit reply codes** and text.
- **Data channel**: separate TCP connection opened per transfer (directory listing / file transfer).
  - Established in **active** mode (`PORT`) or **passive** mode (`PASV`).

### Line discipline

- Commands are typically case-insensitive, but implementations may parse strictly.
- Extra spaces, missing CRLF, embedded `\r`/`\n`, and extremely long lines are good fuzz inputs.
- Pipelining multiple commands without waiting for replies may trigger server-side edge cases.

---

## 2) High-level session state machine

Common server-side states (approximate):

1. **CONNECTED** (after TCP accept)
   - Server greets with `220`.
2. **AUTH_USER** (after `USER`)
   - Expect `PASS` (or reject).
3. **LOGGED_IN** (after successful `USER`/`PASS`)
   - Most filesystem commands are allowed.
4. **DATA_READY** (after `PASV` or `PORT`, before `LIST/RETR/STOR`)
   - Data connection parameters are set.
5. **TRANSFERRING** (after `LIST/RETR/STOR`)
   - Server opens data connection, returns `150`, then `226` on completion (or `425/426` on error).
6. **CLOSED** (after `QUIT` or disconnect)

State-sensitive command behavior:

- `PASS` before `USER` usually yields `503` or `530`.
- `LIST/RETR/STOR` without a valid data setup often yields `425`.
- `CWD`, `DELE`, `RNFR/RNTO`, `MKD/RMD` typically require login.

---

## 3) Common reply codes you will see

- **2xx (success)**
  - `200` Command OK
  - `220` Service ready (greeting)
  - `221` Service closing control connection
  - `226` Closing data connection / transfer successful
  - `230` User logged in
  - `250` Requested file action okay / completed
  - `257` "PATHNAME" created / current directory (server prints a quoted path)
- **3xx (need more info)**
  - `331` User name okay, need password
  - `350` Requested file action pending further information (e.g., `RNFR`)
- **4xx (transient failure)**
  - `425` Can't open data connection
  - `426` Connection closed; transfer aborted
  - `450` File action not taken (busy/unavailable)
- **5xx (permanent failure / syntax / auth)**
  - `500` Syntax error, command unrecognized
  - `501` Syntax error in parameters/arguments
  - `502` Command not implemented
  - `503` Bad sequence of commands
  - `530` Not logged in
  - `550` File action not taken (no such file/permission)

Multi-line replies exist (e.g., `211-...` / `211 End`). Many servers implement them.

---

## 4) Command reference (core set)

All commands are sent on the **control channel**.
The argument grammar is “loose” in many servers; fuzzing should vary separators, quoting, and
path encodings.

### Authentication / session control

- `USER <username>`
  - Typical: `331` then wait for `PASS`, or directly `230` for anonymous/empty pass policies.
- `PASS <password>`
  - Success: `230`; failure: `530`; ordering issues: `503`.
- `QUIT`
  - Typical: `221` then server closes control socket.
- `NOOP`
  - Typical: `200`.
- `SYST`
  - Typical: `215 <system type>`.
- `FEAT` (optional)
  - Often `211-` multi-line listing then `211 End`.
- `HELP [cmd]` (optional)
  - Often `214 ...`.
- `OPTS <name> [value]` (optional)
  - Used by some extensions (e.g., `OPTS UTF8 ON`).

### Working directory & path operations

- `PWD`
  - Typical: `257 "<path>"`.
- `CWD <path>`
  - Typical: `250` on success; `550` on failure.
- `CDUP`
  - Typical: `250` (parent directory).
- `MKD <path>`
  - Typical: `257 "<path>" created`.
- `RMD <path>`
  - Typical: `250` / `550`.

### Directory listing (requires data connection)

- `LIST [path]`
  - Typical flow: `150` then data then `226`.
- `NLST [path]`
  - Similar to `LIST` but names only.
- `STAT [path]`
  - May be control-only or may use data depending on server.

### Transfer type/mode (commonly accepted)

- `TYPE A` (ASCII) / `TYPE I` (binary/image)
  - Typical: `200`.
- `MODE S` (stream) / `STRU F` (file)
  - Typical: `200` or `504` (not implemented).

### Data connection setup

- `PASV`
  - Server replies `227 Entering Passive Mode (h1,h2,h3,h4,p1,p2)`.
  - Data endpoint is `h1.h2.h3.h4` and port \(p1*256 + p2\).
  - Fuzz ideas: malformed tuple, extra fields, negative numbers, large numbers, whitespace.
- `PORT h1,h2,h3,h4,p1,p2`
  - Active mode: client tells server where to connect for data.
  - Typical: `200` on success; `501` on parse error.

### File operations (often require login + data connection for content)

- `RETR <path>` (download)
  - Typical: `150` then data then `226`; `550` if missing/denied.
- `STOR <path>` (upload)
  - Similar transfer flow; errors may yield `553/550`.
- `APPE <path>` (append)
- `REST <offset>` (restart position; used with `RETR/STOR`)
  - Typical: `350` then next transfer resumes; many servers are strict here.
- `SIZE <path>` / `MDTM <path>` (optional)
  - Typical: `213 <size>` / `213 <timestamp>`.
- `DELE <path>`
  - Typical: `250` / `550`.
- Rename sequence:
  - `RNFR <path>` → `350`
  - `RNTO <path>` → `250` / `550`

---

## 5) Minimal “good” session examples

### Example A: login + PWD + QUIT (control-only)

```
S: 220 ...
C: USER test
S: 331 ...
C: PASS test
S: 230 ...
C: PWD
S: 257 "/"
C: QUIT
S: 221 ...
```

### Example B: passive LIST

```
S: 220 ...
C: USER test
S: 331 ...
C: PASS test
S: 230 ...
C: TYPE I
S: 200 ...
C: PASV
S: 227 Entering Passive Mode (127,0,0,1,195,80)
C: LIST
S: 150 ...
S: 226 ...
```

---

## 6) Seed enrichment hints (message types)

For a stateful FTP session, the following **message types** are commonly “missing” in raw seeds
and are good candidates for insertion (depending on current state):

- **Login**: `USER`, `PASS`
- **Environment**: `SYST`, `FEAT`, `TYPE`
- **Directory navigation**: `PWD`, `CWD`, `CDUP`
- **Data setup**: `PASV` or `PORT`
- **Transfer**: `LIST` / `NLST` / `RETR` / `STOR`
- **Cleanup**: `QUIT`

Missing-set examples:

- If a seed contains `LIST` but no prior `PASV/PORT`, insert `PASV`.
- If a seed contains file ops but no login, insert `USER` + `PASS`.

---

## 7) Fuzzing-oriented edge cases & parsing stressors

These are protocol-valid-ish inputs that often exercise server parsing/logic:

- **Oversized arguments**: very long usernames, passwords, paths, or `PORT` tuples.
- **Path tricks**: `..`, repeated slashes, `./`, URL-like strings, mixed separators, quoting.
- **CRLF quirks**: missing `\r`, extra `\r\r\n`, embedded newlines inside arguments.
- **Command confusion**: unknown commands close to valid ones (`USRE`, `PAAS`), mixed-case.
- **Sequence violations**: `PASS` before `USER`, `RNTO` without `RNFR`, `RETR` before data setup.
- **Data connection races**: `PASV` then delay, open/close data sockets early, reuse stale data params.
- **Pipelining**: send `USER\r\nPASS\r\nPWD\r\n` in one burst.

---

## 8) Practical note for this repo’s benchmark harness

The benchmark scripts typically run Bftpd on FTP port 21 and use `afl-fuzz` to generate control
channel inputs. Seeds are usually treated as “structured request sequences” (multiple FTP commands
per test case), consistent with AFLNet-style fuzzing.

