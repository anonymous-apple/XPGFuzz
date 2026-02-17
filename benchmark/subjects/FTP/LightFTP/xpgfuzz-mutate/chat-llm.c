#define _GNU_SOURCE // asprintf
#include <stdio.h>
#include <curl/curl.h>
#include <string.h>
#include <ctype.h>
#include <dirent.h>
#include <unistd.h>
#include <stdlib.h>
#include <time.h>
#include <arpa/inet.h>
#include <math.h>

#include "chat-llm.h"
#include "alloc-inl.h"
#include "hash.h"

// -lcurl -ljson-c -lpcre2-8
// apt install libcurl4-openssl-dev libjson-c-dev libpcre2-dev libpcre2-8-0

#define MAX_TOKENS 2048
#define CONFIDENT_TIMES 3

struct MemoryStruct
{
    char *memory;
    size_t size;
};

static size_t chat_with_llm_helper(void *contents, size_t size, size_t nmemb, void *userp)
{
    size_t realsize = size * nmemb;
    struct MemoryStruct *mem = (struct MemoryStruct *)userp;

    mem->memory = realloc(mem->memory, mem->size + realsize + 1);
    if (mem->memory == NULL)
    {
        /* out of memory! */
        printf("not enough memory (realloc returned NULL)\n");
        return 0;
    }

    memcpy(&(mem->memory[mem->size]), contents, realsize);
    mem->size += realsize;
    mem->memory[mem->size] = 0;

    return realsize;
}

const char *xpgfuzz_llm_get_api_key(void) {
    const char *v = getenv(XPGFUZZ_LLM_API_KEY_ENV);
    return (v && v[0]) ? v : NULL;
}

const char *xpgfuzz_llm_get_base_url(void) {
    const char *v = getenv(XPGFUZZ_LLM_BASE_URL_ENV);
    return (v && v[0]) ? v : XPGFUZZ_LLM_DEFAULT_BASE_URL;
}

const char *xpgfuzz_llm_get_model(void) {
    const char *v = getenv(XPGFUZZ_LLM_MODEL_ENV);
    return (v && v[0]) ? v : XPGFUZZ_LLM_DEFAULT_MODEL;
}

static char *xpgfuzz_build_chat_completions_url(void) {
    const char *base = xpgfuzz_llm_get_base_url();
    size_t n = strlen(base);
    if (n >= strlen("/chat/completions") &&
        strcmp(base + (n - strlen("/chat/completions")), "/chat/completions") == 0) {
        return strdup(base);
    }
    if (n >= 3 && strcmp(base + (n - 3), "/v1") == 0) {
        char *url = NULL;
        asprintf(&url, "%s/chat/completions", base);
        return url;
    }
    char *url = NULL;
    asprintf(&url, "%s/v1/chat/completions", base);
    return url;
}

char *chat_with_llm(char *prompt, char *model, int tries, float temperature)
{
    CURL *curl;
    CURLcode res = CURLE_OK;
    char *answer = NULL;
    char *url = NULL;
    char *auth_header = NULL;
    char *content_header = "Content-Type: application/json";
    char *accept_header = "Accept: application/json";
    char *data = NULL;

    const char *api_key = xpgfuzz_llm_get_api_key();
    if (!api_key) {
        fprintf(stderr,
                "[xpgfuzz] Missing %s. Set it in your environment (see .env.example).\n",
                XPGFUZZ_LLM_API_KEY_ENV);
        return NULL;
    }
    url = xpgfuzz_build_chat_completions_url();
    asprintf(&auth_header, "Authorization: Bearer %s", api_key);
    
    // Build JSON request properly using json-c library
    json_object *request_obj = json_object_new_object();
    const char *model_name =
        (model && model[0] && strcmp(model, "instruct") != 0) ? model : xpgfuzz_llm_get_model();
    json_object_object_add(request_obj, "model", json_object_new_string(model_name));
    // gpt-3.5-turbo，2023年3月问世的
    // DeepSeek-V3.1-Fast，DeepSeek-V3 的智能水平是显著高于 GPT-3.5 Turbo 的，它们属于不同梯队的模型。它的设计目标是对标 GPT-4o 和 Claude 3.5 Sonnet 这一级别的顶尖模型。
    
    
    // Create messages array
    json_object *messages_array = json_object_new_array();
    json_object *message_obj = json_object_new_object();
    json_object_object_add(message_obj, "role", json_object_new_string("user"));
    json_object_object_add(message_obj, "content", json_object_new_string(prompt));
    json_object_array_add(messages_array, message_obj);
    json_object_object_add(request_obj, "messages", messages_array);
    
    json_object_object_add(request_obj, "max_tokens", json_object_new_int(MAX_TOKENS));
    json_object_object_add(request_obj, "temperature", json_object_new_double(temperature));
    
    data = (char *)json_object_to_json_string(request_obj);
    data = strdup(data); // Make a copy since json_object will be freed later
    curl_global_init(CURL_GLOBAL_DEFAULT);
    do
    {
        struct MemoryStruct chunk;

        chunk.memory = malloc(1); /* will be grown as needed by the realloc above */
        chunk.size = 0;           /* no data at this point */

        curl = curl_easy_init();
        if (curl)
        {
            struct curl_slist *headers = NULL;
            headers = curl_slist_append(headers, auth_header);
            headers = curl_slist_append(headers, content_header);
            headers = curl_slist_append(headers, accept_header);

            curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
            curl_easy_setopt(curl, CURLOPT_POSTFIELDS, data);
            curl_easy_setopt(curl, CURLOPT_URL, url);
            curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, chat_with_llm_helper);
            curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void *)&chunk);

            res = curl_easy_perform(curl);

            if (res == CURLE_OK)
            {
                json_object *jobj = json_tokener_parse(chunk.memory);

                // Check if the "choices" key exists
                if (json_object_object_get_ex(jobj, "choices", NULL))
                {
                    json_object *choices = json_object_object_get(jobj, "choices");
                    json_object *first_choice = json_object_array_get_idx(choices, 0);
                    const char *data;

                    json_object *jobj4 = json_object_object_get(first_choice, "message");
                    json_object *jobj5 = json_object_object_get(jobj4, "content");
                    data = json_object_get_string(jobj5);
                    
                    if (data[0] == '\n')
                        data++;
                    answer = strdup(data);
                }
                else
                {
                    printf("Error response is: %s\n", chunk.memory);
                    sleep(2); // Sleep for a small amount of time to ensure that the service can recover
                }
                json_object_put(jobj);
            }
            else
            {
                printf("Error: %s\n", curl_easy_strerror(res));
            }

            curl_slist_free_all(headers);
            curl_easy_cleanup(curl);
        }

        free(chunk.memory);
    } while ((res != CURLE_OK || answer == NULL) && (--tries > 0));

    // Free JSON object and data
    if (request_obj != NULL)
    {
        json_object_put(request_obj);
    }
    if (data != NULL)
    {
        free(data);
    }
    if (auth_header != NULL) {
        free(auth_header);
    }
    if (url != NULL) {
        free(url);
    }

    curl_global_cleanup();
    return answer;
}

char *construct_prompt_stall(char *protocol_name, char *examples, char *history)
{
    char *template = "CRITICAL: Return ONLY the raw protocol command, NO explanations, NO analysis, NO markdown.\\n\\n"
                     "Protocol: %s\\n\\n"
                     "Communication History:\\n"
                     "\\\"\\\"\\\"\\n%s\\\"\\\"\\\"\\n\\n"
                     "Desired format example:\\n%s\\n\\n"
                     "Task: Generate the next proper client request that can affect the server's state.\\n"
                     "Output: Return ONLY the raw command line (e.g., \"PASS password\\r\\n\" or \"CWD /path\\r\\n\"), nothing else.";

    char *prompt = NULL;
    asprintf(&prompt, template, protocol_name, protocol_name, protocol_name, examples, history);

    char *final_prompt = NULL;

    asprintf(&final_prompt, "[{\"role\": \"system\", \"content\": \"You are a helpful assistant.\"}, {\"role\": \"user\", \"content\": \"%s\"}]", prompt);

    free(prompt);

    return final_prompt;
}


// char *construct_enhanced_prompt_stall(char *protocol_name, char *examples, char *history)  
// {  
//     char *enhanced_template =   
//         "You are an expert %s protocol fuzzer with deep knowledge of network protocols and vulnerability discovery. "  
//         "Your goal is to generate the next client request that will maximize code coverage and potentially trigger edge cases or vulnerabilities.\\n\\n"  
          
//         "COMMUNICATION HISTORY:\\n"  
//         "The following shows the complete request-response sequence between client and server:\\n"  
//         "\\\"\\\"\\\"%s\\\"\\\"\\\"\\n\\n"  
          
//         "DESIRED OUTPUT FORMAT:\\n"  
//         "%s\\n"  
          
//         "GENERATION GUIDELINES:\\n"  
//         "1. Analyze the communication flow to identify the current protocol state\\n"  
//         "2. Consider edge cases: malformed headers, boundary values, unexpected sequences\\n"  
//         "3. Focus on requests that could trigger new code paths or error conditions\\n"  
//         "4. Maintain protocol syntax while exploring boundary conditions\\n"  
//         "5. Generate ONE complete, well-formed %s request\\n\\n"  
          
//         "Generate the next proper client request that can affect the server's state:";  
  
//     char *prompt = NULL;  
//     asprintf(&prompt, enhanced_template, protocol_name, history, examples, protocol_name);  
  
//     char *final_prompt = NULL;  
//     asprintf(&final_prompt,   
//              "[{\"role\": \"system\", \"content\": \"You are an expert network protocol security researcher and fuzzing specialist.\"}, "  
//              "{\"role\": \"user\", \"content\": \"%s\"}]",   
//              prompt);  
  
//     free(prompt);  
//     return final_prompt;  
// }

char *construct_prompt_for_templates(char *protocol_name, char **final_msg)
{
    // Give one example for learning formats with type constraints
    char *prompt_rtsp_example = "For the RTSP protocol, the DESCRIBE client request template is:\\n"
                                "DESCRIBE: [\\\"DESCRIBE <<PATH>>\\\\r\\\\n\\\","
                                "\\\"CSeq: <<INTEGER:1-65535>>\\\\r\\\\n\\\","
                                "\\\"User-Agent: <<STRING:1-256>>\\\\r\\\\n\\\","
                                "\\\"Accept: <<ENUM:application/sdp,application/x-rtsp-tunnelled>>\\\\r\\\\n\\\","
                                "\\\"\\\\r\\\\n\\\"]\\n\\n"
                                "Note: Use type constraints in the format:\\n"
                                "- <<INTEGER:min-max>> for integer ranges (e.g., <<INTEGER:0-65535>>)\\n"
                                "- <<STRING:min_len-max_len>> for string length ranges (e.g., <<STRING:1-256>>)\\n"
                                "- <<ENUM:val1,val2,val3>> for enumerated values (e.g., <<ENUM:GET,POST,PUT>>)\\n"
                                "- <<IP>> for IP addresses\\n"
                                "- <<PATH>> for file paths\\n"
                                "- <<HEX>> for hexadecimal values\\n"
                                "- <<VALUE>> for unconstrained values (backward compatibility)";

    char *prompt_http_example = "For the HTTP protocol, the GET client request template is:\\n"
                                "GET: [\\\"GET <<PATH>>\\\\r\\\\n\\\","
                                "\\\"Host: <<IP>>\\\\r\\\\n\\\","
                                "\\\"User-Agent: <<STRING:1-512>>\\\\r\\\\n\\\","
                                "\\\"\\\\r\\\\n\\\"]";  //少样本学习

    char *consistency_guidelines = "\\n\\nCRITICAL CONSISTENCY REQUIREMENTS:\\n"
                                   "1. Use the SAME format for the same command across ALL requests\\n"
                                   "2. If a parameter is optional, ALWAYS include it in the template with the constraint marker\\n"
                                   "3. Maintain consistent spacing: use exactly ONE space between command and parameters\\n"
                                   "4. Use consistent constraint types for the same field (e.g., always use <<INTEGER:0-255>> not <<STRING:7-15>> for ports)\\n"
                                   "5. For commands with multiple variants, choose ONE canonical format and use it consistently\\n"
                                   "6. Enum values should include ALL valid options consistently across all templates";

    char *msg = NULL;
    asprintf(&msg, "%s\\n%s%s\\nFor the %s protocol, all of client request templates are (use type constraints where appropriate):", prompt_rtsp_example, prompt_http_example, consistency_guidelines, protocol_name);
    *final_msg = msg;
    /** Format of prompt_grammars
    prompt_grammars = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": msg}
    ]
     **/
    char *prompt_grammars = NULL;

    asprintf(&prompt_grammars, "[{\"role\": \"system\", \"content\": \"You are a helpful assistant specialized in network protocol analysis. Always use type constraints in templates when you can infer the value type from the protocol specification. CRITICAL: Maintain strict format consistency across all templates - use identical formats for the same commands and fields.\"}, {\"role\": \"user\", \"content\": \"%s\"}]", msg);

    return prompt_grammars;
}

char *construct_prompt_for_remaining_templates(char *protocol_name, char *first_question, char *first_answer)
{
    char *second_question = NULL;
    asprintf(&second_question, "For the %s protocol, other templates of client requests are (use type constraints where appropriate, same format as before):", protocol_name);

    json_object *answer_str = json_object_new_string(first_answer);
    // printf("The First Question\n%s\n\n", first_question);
    // printf("The First Answer\n%s\n\n", first_answer);
    // printf("The Second Question\n%s\n\n", second_question);
    const char *answer_str_escaped = json_object_to_json_string(answer_str);

    char *prompt = NULL;

    asprintf(&prompt,
             "["
             "{\"role\": \"system\", \"content\": \"You are a helpful assistant.\"},"
             "{\"role\": \"user\", \"content\": \"%s\"},"
             "{\"role\": \"assistant\", \"content\": %s },"
             "{\"role\": \"user\", \"content\": \"%s\"}"
             "]",
             first_question, answer_str_escaped, second_question);

    json_object_put(answer_str);
    free(second_question);

    return prompt;
}

// Extract command from LLM response (handles explanations, markdown, etc.)
static char *extract_command_from_response(const char *response, size_t response_len) {
    if (!response || response_len == 0) return NULL;
    
    // Strategy 1: Look for code blocks (```...```)
    const char *code_start = strstr(response, "```");
    if (code_start) {
        code_start += 3; // Skip ```
        // Skip language identifier
        while (code_start < response + response_len && 
               (*code_start == '\n' || *code_start == ' ' || 
                (*code_start >= 'a' && *code_start <= 'z') ||
                (*code_start >= 'A' && *code_start <= 'Z'))) {
            code_start++;
        }
        const char *code_end = strstr(code_start, "```");
        if (code_end) {
            size_t len = code_end - code_start;
            char *result = malloc(len + 1);
            strncpy(result, code_start, len);
            result[len] = '\0';
            // Extract first line (the command)
            char *newline = strchr(result, '\n');
            if (newline) *newline = '\0';
            return result;
        }
    }
    
    // Strategy 2: Look for "Request-1:", "Final Answer:", etc.
    const char *markers[] = {
        "Request-1:",
        "request-1:",
        "Final Answer:",
        "final answer:",
        "Answer:",
        "answer:",
        "Command:",
        "command:",
        "Next request:",
        "next request:"
    };
    
    for (int i = 0; i < sizeof(markers) / sizeof(markers[0]); i++) {
        const char *marker = strstr(response, markers[i]);
        if (marker) {
            marker += strlen(markers[i]);
            // Skip whitespace
            while (marker < response + response_len && 
                   (*marker == ' ' || *marker == '\n' || *marker == '\r' || *marker == '\t')) {
                marker++;
            }
            
            // Extract until next newline or end
            const char *end = marker;
            while (end < response + response_len && *end != '\n' && *end != '\r' && *end != '\0') {
                end++;
            }
            
            size_t len = end - marker;
            if (len > 0) {
                char *result = malloc(len + 1);
                strncpy(result, marker, len);
                result[len] = '\0';
                return result;
            }
        }
    }
    
    // Strategy 3: Look for protocol commands from FTP, SMTP, RTSP, SIP, HTTP, DAAP
    // Pattern: COMMAND followed by optional parameters and \r\n
    const char *protocol_commands[] = {
        // FTP commands
        "USER ", "PASS ", "CWD ", "RETR ", "STOR ", "LIST ", "DELE ", 
        "MKD ", "RMD ", "RNFR ", "RNTO ", "TYPE ", "PASV ", "PORT ",
        "QUIT", "SYST", "NOOP", "PWD", "HELP", "STAT", "FEAT",
        "APPE ", "REST ", "SIZE ", "MDTM ", "NLST ", "STOU ", "ACCT ",
        "CDUP", "XCWD ", "XPWD", "XMKD ", "XRMD ", "EPRT ", "EPSV ",
        "AUTH ", "PBSZ ", "PROT ", "MODE ", "STRU ", "ALLO ", "SITE ",
        "MLSD ", "MLST ", "OPTS ", "LPRT ", "LPSV ",
        // SMTP commands
        "HELO ", "EHLO ", "MAIL FROM:", "RCPT TO:", "DATA", "QUIT",
        "RSET", "VRFY ", "EXPN ", "HELP", "NOOP", "STARTTLS", "AUTH ",
        // RTSP commands
        "DESCRIBE ", "ANNOUNCE ", "GET_PARAMETER ", "OPTIONS ", "PAUSE ",
        "PLAY ", "RECORD ", "REDIRECT ", "SETUP ", "SET_PARAMETER ",
        "TEARDOWN ", "RTSP/",
        // SIP methods
        "INVITE ", "ACK ", "BYE ", "CANCEL ", "REGISTER ", "OPTIONS ",
        "PRACK ", "SUBSCRIBE ", "NOTIFY ", "PUBLISH ", "INFO ", "REFER ",
        "UPDATE ", "MESSAGE ", "SIP/",
        // HTTP methods
        "GET ", "POST ", "PUT ", "DELETE ", "HEAD ", "OPTIONS ",
        "PATCH ", "TRACE ", "CONNECT ", "HTTP/",
        // HTTP/DAAP headers (common request headers)
        "Host:", "Content-Type:", "Content-Length:", "User-Agent:",
        "Accept:", "Authorization:", "Cookie:", "Referer:",
        "Connection:", "Upgrade:", "DAAP/"
    };
    
    for (int i = 0; i < sizeof(protocol_commands) / sizeof(protocol_commands[0]); i++) {
        const char *cmd = strstr(response, protocol_commands[i]);
        if (cmd) {
            // Find the end of the command line
            const char *line_end = cmd;
            while (line_end < response + response_len && 
                   *line_end != '\n' && *line_end != '\r' && *line_end != '\0') {
                line_end++;
            }
            
            size_t len = line_end - cmd;
            if (len > 0 && len < 200) { // Reasonable command length
                char *result = malloc(len + 1);
                strncpy(result, cmd, len);
                result[len] = '\0';
                // Trim trailing whitespace
                char *trim = result + len - 1;
                while (trim > result && (*trim == ' ' || *trim == '\t')) {
                    *trim = '\0';
                    trim--;
                }
                return result;
            }
        }
    }
    
    // Strategy 4: Original regex-based extraction (fallback)
    int errornumber;
    size_t erroroffset;
    pcre2_code *extracter = pcre2_compile("\r?\n?.*?\r?\n", PCRE2_ZERO_TERMINATED, 0, &errornumber, &erroroffset, NULL);
    if (extracter) {
        pcre2_match_data *match_data = pcre2_match_data_create_from_pattern(extracter, NULL);
        int rc = pcre2_match(extracter, response, response_len, 0, 0, match_data, NULL);
        char *res = NULL;
        if (rc >= 0) {
            size_t *ovector = pcre2_get_ovector_pointer(match_data);
            if (ovector[1] < response_len) {
                res = strdup(response + ovector[1]);
            }
        }
        pcre2_match_data_free(match_data);
        pcre2_code_free(extracter);
        if (res) return res;
    }
    
    return NULL;
}

char *extract_stalled_message(char *message, size_t message_len)
{
    if (!message || message_len == 0) return NULL;
    
    // Use improved extraction function
    char *extracted = extract_command_from_response(message, message_len);
    
    if (extracted) {
        // Clean up: remove any remaining markdown, explanations
        char *cleaned = extracted;
        
        // Remove leading/trailing whitespace
        while (*cleaned == ' ' || *cleaned == '\n' || *cleaned == '\r' || *cleaned == '\t') {
            cleaned++;
        }
        char *end = cleaned + strlen(cleaned) - 1;
        while (end > cleaned && (*end == ' ' || *end == '\n' || *end == '\r' || *end == '\t')) {
            *end = '\0';
            end--;
        }
        
        // Remove markdown code markers if present
        if (cleaned[0] == '`' && cleaned[1] == '`' && cleaned[2] == '`') {
            cleaned += 3;
            char *newline = strchr(cleaned, '\n');
            if (newline) cleaned = newline + 1;
        }
        
        // If we modified the pointer, create new string
        if (cleaned != extracted) {
            char *result = strdup(cleaned);
            free(extracted);
            return result;
        }
        
        return extracted;
    }
    
    // Fallback: original simple extraction
    int errornumber;
    size_t erroroffset;
    pcre2_code *extracter = pcre2_compile("\r?\n?.*?\r?\n", PCRE2_ZERO_TERMINATED, 0, &errornumber, &erroroffset, NULL);
    pcre2_match_data *match_data = pcre2_match_data_create_from_pattern(extracter, NULL);
    int rc = pcre2_match(extracter, message, message_len, 0, 0, match_data, NULL);
    char *res = NULL;
    if (rc >= 0)
    {
        size_t *ovector = pcre2_get_ovector_pointer(match_data);
        if (ovector[1] < message_len) {
            res = strdup(message + ovector[1]);
        }
    }

    pcre2_match_data_free(match_data);
    pcre2_code_free(extracter);

    return res;
}

char *format_request_message(char *message)
{

    int message_len = strlen(message);
    int max_len = message_len;
    int res_len = 0;
    char *res = ck_alloc(message_len * sizeof(char));
    for (int i = 0; i < message_len; i++)
    {
        // If an \n is not padded with an \r before, we add it
        if (message[i] == '\n' && (i == 0 || (message[i - 1] != '\r')))
        {
            if (res_len == max_len)
            {
                res = ck_realloc(res, max_len + 10);
                max_len += 10;
            }
            res[res_len++] = '\r';
        }

        if (res_len == max_len)
        {
            res = ck_realloc(res, max_len + 10);
            max_len += 10;
        }
        res[res_len++] = message[i];
    }

    // Add \r\n\r\n to ensure that the packet is accepted
    for (int i = 0; i < 2; i++)
    {
        if (res_len == max_len)
        {
            res = ck_realloc(res, max_len + 10);
            max_len += 10;
        }
        res[res_len++] = '\r';
        if (res_len == max_len)
        {
            res = ck_realloc(res, max_len + 10);
            max_len += 10;
        }
        res[res_len++] = '\n';
    }

    if (res_len == max_len)
    {
        res = ck_realloc(res, max_len + 1);
        max_len++;
    }
    res[res_len++] = '\0';
    free(message);
    return res;
}

//获取协议的所有状态
char *construct_prompt_for_protocol_message_types(char *protocol_name)
{
    /***
     * Prompt to ask the protocol states as follow:
     * ```
     * In the RTSP protocol, the protocol states are:
     *
     * Desired format:
     * <comma_separated_list_of_states_in_uppercase>
     * ```
     * ***/
    char *prompt = NULL;

    // transfer the prompt into string
    asprintf(&prompt, "In the %s protocol, the message types are: \\n\\nDesired format:\\n<comma_separated_list_of_states_in_uppercase_and_without_whitespaces>", protocol_name);

    return prompt;
}

char *construct_prompt_for_requests_to_states(const char *protocol_name,
                                              const char *protocol_state,
                                              const char *example_requests)
{
    /***
     Prompt to ask the sequence of client requests to reach a protocol state as follows:
        ```
        In the RTSP protocol, if the server just starts, to reach the PLAYING state, the sequence of client requests can be:
        DESCRIBE rtsp://127.0.0.1:8554/aacAudioTest RTSP/1.0
        CSeq: 2
        User-Agent: ./testRTSPClient (LIVE555 Streaming Media v2018.08.28)
        Accept: application/sdp

        SETUP rtsp://127.0.0.1:8554/aacAudioTest/track1 RTSP/1.0
        CSeq: 3
        User-Agent: ./testRTSPClient (LIVE555 Streaming Media v2018.08.28)
        Transport: RTP/AVP;unicast;client_port=38784-38785

        PLAY rtsp://127.0.0.1:8554/aacAudioTest/ RTSP/1.0
        CSeq: 4
        User-Agent: ./testRTSPClient (LIVE555 Streaming Media v2018.08.28)
        Session: 000022B8
        Range: npt=0.000-

        Similarly, in the RTSP protocol, if the server just starts, to reach the RECORD state, the sequence of client requests can be:
     ***/

    // Transfer formats of example_requests
    json_object *example_requests_json = json_object_new_string(example_requests);
    const char *example_requests_json_str = json_object_to_json_string(example_requests_json);

    json_object *protocol_state_json = json_object_new_string(protocol_state);
    const char *protocol_state_json_str = json_object_to_json_string(protocol_state_json);

    char *prompt = NULL;

    int example_request_len = strlen(example_requests_json_str) - 2;
    if (example_request_len > EXAMPLE_SEQUENCE_PROMPT_LENGTH)
    {
        example_request_len = EXAMPLE_SEQUENCE_PROMPT_LENGTH;
    }

    asprintf(&prompt,
             "In the %s protocol, if the server just starts, to reach the INIT state, the sequence of client requests can be:\\n"
             "%.*s\\nSimilarly, in the %s protocol, if the server just starts, to reach the %.*s state, the sequence of client requests can be:\\n",
             protocol_name,
             example_request_len,
             example_requests_json_str + 1,
             protocol_name,
             (int)strlen(protocol_state_json_str) - 2,
             protocol_state_json_str + 1);

    json_object_put(protocol_state_json);
    json_object_put(example_requests_json);

    return prompt;
}

void extract_message_grammars(char *answers, klist_t(gram) * grammar_list)
{

    char *ptr = answers;
    int len = strlen(answers);

    while (ptr < answers + len)
    {
        char *start = strchr(ptr, '[');
        if (start == NULL)
            break;
        char *end = strchr(start, ']');
        if (end == NULL)
            break;
        int count = end - start + 1;
        char *temp = (char *)ck_alloc(count + 1);
        strncpy(temp, start, count);
        temp[count] = '\0';
        ptr = end + 1;

        // conver temp to json object and save it to the list
        json_object *jobj = json_tokener_parse(temp);
        // Only add valid JSON arrays to the list
        if (jobj != NULL && json_object_get_type(jobj) == json_type_array)
        {
            *kl_pushp(gram, grammar_list) = jobj;
        }
        else
        {
            // Free invalid JSON object
            if (jobj != NULL)
                json_object_put(jobj);
        }
        ck_free(temp);

        // printf("%s\n", temp);
    }
}

// Helper function to normalize constraint string by removing spaces
// Converts "INTEGER : 0 - 65535" -> "INTEGER:0-65535"
static char *normalize_constraint_content(const char *str)
{
    if (!str) return NULL;
    
    size_t len = strlen(str);
    char *normalized = (char *)ck_alloc(len + 1);
    if (!normalized) return NULL;
    
    int i = 0, j = 0;
    int last_was_space = 0;
    
    while (i < len)
    {
        char c = str[i];
        
        // Skip spaces, but preserve structure
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r')
        {
            last_was_space = 1;
            i++;
            continue;
        }
        
        // If previous char was space and current is ':' or '-', skip the space
        // This handles "INTEGER :" -> "INTEGER:" and "0 - 65535" -> "0-65535"
        if (last_was_space && (c == ':' || c == '-'))
        {
            // Don't add the space, just add the current char
            normalized[j++] = c;
            last_was_space = 0;
            i++;
            continue;
        }
        
        // If current char is ':' or '-' and previous was space, we already handled it
        // Otherwise, add the char
        normalized[j++] = c;
        last_was_space = 0;
        i++;
    }
    
    normalized[j] = '\0';
    return normalized;
}

// Helper function to extract constraint from matched group
// Robustly handles spaces in constraint markers
static type_constraint_t *extract_constraint_from_match(const char *str, PCRE2_SIZE start, PCRE2_SIZE end)
{
    if (start == (PCRE2_SIZE)-1 || end == (PCRE2_SIZE)-1 || start >= end)
        return NULL;
    
    size_t len = end - start;
    char *constraint_str = (char *)ck_alloc(len + 1);
    strncpy(constraint_str, str + start, len);
    constraint_str[len] = '\0';
    
    // Trim leading and trailing whitespace from constraint string
    // This handles cases like " INTEGER:0-65535 " -> "INTEGER:0-65535"
    char *trimmed = constraint_str;
    while (*trimmed == ' ' || *trimmed == '\t' || *trimmed == '\n' || *trimmed == '\r')
        trimmed++;
    
    char *end_ptr = trimmed + strlen(trimmed) - 1;
    while (end_ptr > trimmed && (*end_ptr == ' ' || *end_ptr == '\t' || *end_ptr == '\n' || *end_ptr == '\r'))
        end_ptr--;
    end_ptr[1] = '\0';
    
    // Normalize constraint content: remove spaces around ':' and '-'
    // This handles "INTEGER : 0 - 65535" -> "INTEGER:0-65535"
    char *normalized_content = normalize_constraint_content(trimmed);
    const char *content_to_parse = normalized_content ? normalized_content : trimmed;
    
    // Parse the normalized constraint
    // Note: parse_constraint expects the constraint content without <<...>>
    // e.g., "INTEGER:0-65535" not "<<INTEGER:0-65535>>"
    type_constraint_t *constraint = NULL;
    if (strlen(content_to_parse) > 0)
    {
        // Add <<...>> wrapper if not present (for backward compatibility)
        char *wrapped = NULL;
        if (content_to_parse[0] != '<' || content_to_parse[1] != '<')
        {
            asprintf(&wrapped, "<<%s>>", content_to_parse);
            constraint = parse_constraint(wrapped);
            free(wrapped);
        }
        else
        {
            constraint = parse_constraint(content_to_parse);
        }
    }
    
    if (normalized_content) ck_free(normalized_content);
    ck_free(constraint_str);
    return constraint;
}

int parse_pattern(pcre2_code *replacer, pcre2_match_data *match_data, const char *str, size_t len, char *pattern, type_constraint_t **out_constraint)
{
    size_t pattern_start_len = strlen(pattern);
    strcat(pattern, "(?:");
    // offset == 3;
    int rc = pcre2_match(replacer, str, len, 0, 0, match_data, NULL);

    if (rc < 0)
    {
        switch (rc)
        {
        case PCRE2_ERROR_NOMATCH:
            // printf("No match for %s!\n", str);
            break;
        default:
            // printf("Matching error %d\n", rc);
            break;
        }
        // Restore pattern to original state for fault tolerance
        pattern[pattern_start_len] = '\0';
        // Don't free match_data and replacer here - they are managed by caller
        // This allows fault-tolerant processing to continue with other fields
        if (out_constraint) *out_constraint = NULL;
        return 0;
    }
    // printf("RC is %d\n",rc);
    PCRE2_SIZE *ovector = pcre2_get_ovector_pointer(match_data);
    // for(int i = 1; i<rc;i++){
    //     printf("Start %d, end %d\n",ovector[2*i],ovector[2*i+1]);
    // }

    if (rc == 4)
    { // matched the first option - there is a special value
        strncat(pattern, str + ovector[2], ovector[3] - ovector[2]);
        // offset += ovector[3] - ovector[2];

        // Extract constraint from the matched value (group 2)
        if (out_constraint)
        {
            *out_constraint = extract_constraint_from_match(str, ovector[4], ovector[5]);
        }

        strcat(pattern, "(.*)");
        // offset += 3;

        strncat(pattern, str + ovector[6], ovector[7] - ovector[6]);
        // offset += ovector[7] - ovector[6];
    }
    else if (rc == 5)
    {
        // matched the second option - there is no special value
        strncat(pattern, str + ovector[8], ovector[9] - ovector[8]);
        if (out_constraint) *out_constraint = NULL;
        // offset += ovector[9] - ovector[8];
    }
    else
    {
        FATAL("Regex groups were updated but not the handling code.");
    }
    strcat(pattern, ")");
    return 1;
}

// Global storage for pattern constraints
// Maps pattern pointer to array of constraints for each capture group
static khash_t(pattern_constraints_map) *pattern_constraints_storage = NULL;

// Initialize pattern constraints storage
static void init_pattern_constraints_storage(void)
{
    if (pattern_constraints_storage == NULL)
    {
        pattern_constraints_storage = kh_init(pattern_constraints_map);
    }
}

// Store constraints for a pattern
static void store_pattern_constraints(pcre2_code **patterns, type_constraint_t **header_constraints, int header_count, type_constraint_t **field_constraints, int field_count)
{
    init_pattern_constraints_storage();
    
    // Use pattern pointer as key
    khint_t k;
    int ret;
    k = kh_put(pattern_constraints_map, pattern_constraints_storage, (void *)patterns, &ret);
    
    // Allocate structure to store constraints
    pattern_with_constraints_t *pc = (pattern_with_constraints_t *)ck_alloc(sizeof(pattern_with_constraints_t));
    pc->patterns = patterns;
    pc->header_constraints = header_constraints;
    pc->field_constraints = field_constraints;
    pc->header_constraint_count = header_count;
    pc->field_constraint_count = field_count;
    
    kh_value(pattern_constraints_storage, k) = pc;
    
    // Print stored constraints for debugging
    printf("\n[约束哈希表] 存储约束信息:\n");
    printf("  模式指针: %p\n", (void *)patterns);
    printf("  消息头约束数量: %d\n", header_count);
    printf("  字段约束数量: %d\n", field_count);
    
    // Print header constraints
    if (header_count > 0 && header_constraints) {
        printf("  消息头约束:\n");
        for (int i = 0; i < header_count; i++) {
            if (header_constraints[i]) {
                type_constraint_t *c = header_constraints[i];
                printf("    [%d] 类型: ", i);
                switch (c->type) {
                    case CONSTRAINT_NONE:
                        printf("NONE\n");
                        break;
                    case CONSTRAINT_INTEGER:
                        printf("INTEGER [%d-%d]\n", 
                               c->constraint.integer_range.min,
                               c->constraint.integer_range.max);
                        break;
                    case CONSTRAINT_STRING:
                        printf("STRING [长度: %d-%d]\n",
                               c->constraint.string_range.min_len,
                               c->constraint.string_range.max_len);
                        break;
                    case CONSTRAINT_ENUM:
                        printf("ENUM [%d个值: ", c->constraint.enum_values.count);
                        for (int j = 0; j < c->constraint.enum_values.count; j++) {
                            printf("%s", c->constraint.enum_values.values[j]);
                            if (j < c->constraint.enum_values.count - 1) printf(", ");
                        }
                        printf("]\n");
                        break;
                    case CONSTRAINT_IP:
                        printf("IP\n");
                        break;
                    case CONSTRAINT_PATH:
                        printf("PATH\n");
                        break;
                    case CONSTRAINT_HEX:
                        printf("HEX\n");
                        break;
                    default:
                        printf("UNKNOWN(%d)\n", c->type);
                        break;
                }
            }
        }
    }
    
    // Print field constraints
    if (field_count > 0 && field_constraints) {
        printf("  字段约束:\n");
        for (int i = 0; i < field_count; i++) {
            if (field_constraints[i]) {
                type_constraint_t *c = field_constraints[i];
                printf("    [%d] 类型: ", i);
                switch (c->type) {
                    case CONSTRAINT_NONE:
                        printf("NONE\n");
                        break;
                    case CONSTRAINT_INTEGER:
                        printf("INTEGER [%d-%d]\n", 
                               c->constraint.integer_range.min,
                               c->constraint.integer_range.max);
                        break;
                    case CONSTRAINT_STRING:
                        printf("STRING [长度: %d-%d]\n",
                               c->constraint.string_range.min_len,
                               c->constraint.string_range.max_len);
                        break;
                    case CONSTRAINT_ENUM:
                        printf("ENUM [%d个值: ", c->constraint.enum_values.count);
                        for (int j = 0; j < c->constraint.enum_values.count; j++) {
                            printf("%s", c->constraint.enum_values.values[j]);
                            if (j < c->constraint.enum_values.count - 1) printf(", ");
                        }
                        printf("]\n");
                        break;
                    case CONSTRAINT_IP:
                        printf("IP\n");
                        break;
                    case CONSTRAINT_PATH:
                        printf("PATH\n");
                        break;
                    case CONSTRAINT_HEX:
                        printf("HEX\n");
                        break;
                    default:
                        printf("UNKNOWN(%d)\n", c->type);
                        break;
                }
            }
        }
    }
    printf("\n");
}

// Print all constraints in the storage hash table
void print_all_constraints_storage(void)
{
    if (pattern_constraints_storage == NULL) {
        printf("[约束哈希表] 哈希表为空\n");
        return;
    }
    
    printf("\n========== [约束哈希表] 完整内容 ==========\n");
    printf("哈希表大小: %u\n", kh_size(pattern_constraints_storage));
    
    khint_t k;
    int count = 0;
    for (k = kh_begin(pattern_constraints_storage); k != kh_end(pattern_constraints_storage); ++k) {
        if (kh_exist(pattern_constraints_storage, k)) {
            count++;
            void *patterns_key = kh_key(pattern_constraints_storage, k);
            pattern_with_constraints_t *pc = kh_value(pattern_constraints_storage, k);
            
            printf("\n--- 条目 %d ---\n", count);
            printf("Key (模式指针): %p\n", patterns_key);
            printf("消息头约束数量: %d\n", pc->header_constraint_count);
            printf("字段约束数量: %d\n", pc->field_constraint_count);
            
            // Print header constraints
            if (pc->header_constraint_count > 0 && pc->header_constraints) {
                printf("消息头约束:\n");
                for (int i = 0; i < pc->header_constraint_count; i++) {
                    if (pc->header_constraints[i]) {
                        type_constraint_t *c = pc->header_constraints[i];
                        printf("  [%d] ", i);
                        switch (c->type) {
                            case CONSTRAINT_INTEGER:
                                printf("INTEGER [%d-%d]\n", 
                                       c->constraint.integer_range.min,
                                       c->constraint.integer_range.max);
                                break;
                            case CONSTRAINT_STRING:
                                printf("STRING [长度: %d-%d]\n",
                                       c->constraint.string_range.min_len,
                                       c->constraint.string_range.max_len);
                                break;
                            case CONSTRAINT_ENUM:
                                printf("ENUM [%d个值: ", c->constraint.enum_values.count);
                                for (int j = 0; j < c->constraint.enum_values.count; j++) {
                                    printf("%s", c->constraint.enum_values.values[j]);
                                    if (j < c->constraint.enum_values.count - 1) printf(", ");
                                }
                                printf("]\n");
                                break;
                            case CONSTRAINT_IP:
                                printf("IP\n");
                                break;
                            case CONSTRAINT_PATH:
                                printf("PATH\n");
                                break;
                            case CONSTRAINT_HEX:
                                printf("HEX\n");
                                break;
                            default:
                                printf("NONE/UNKNOWN\n");
                                break;
                        }
                    }
                }
            }
            
            // Print field constraints
            if (pc->field_constraint_count > 0 && pc->field_constraints) {
                printf("字段约束:\n");
                for (int i = 0; i < pc->field_constraint_count; i++) {
                    if (pc->field_constraints[i]) {
                        type_constraint_t *c = pc->field_constraints[i];
                        printf("  [%d] ", i);
                        switch (c->type) {
                            case CONSTRAINT_INTEGER:
                                printf("INTEGER [%d-%d]\n", 
                                       c->constraint.integer_range.min,
                                       c->constraint.integer_range.max);
                                break;
                            case CONSTRAINT_STRING:
                                printf("STRING [长度: %d-%d]\n",
                                       c->constraint.string_range.min_len,
                                       c->constraint.string_range.max_len);
                                break;
                            case CONSTRAINT_ENUM:
                                printf("ENUM [%d个值: ", c->constraint.enum_values.count);
                                for (int j = 0; j < c->constraint.enum_values.count; j++) {
                                    printf("%s", c->constraint.enum_values.values[j]);
                                    if (j < c->constraint.enum_values.count - 1) printf(", ");
                                }
                                printf("]\n");
                                break;
                            case CONSTRAINT_IP:
                                printf("IP\n");
                                break;
                            case CONSTRAINT_PATH:
                                printf("PATH\n");
                                break;
                            case CONSTRAINT_HEX:
                                printf("HEX\n");
                                break;
                            default:
                                printf("NONE/UNKNOWN\n");
                                break;
                        }
                    }
                }
            }
        }
    }
    
    printf("\n========== [约束哈希表] 总计 %d 个条目 ==========\n\n", count);
}

// Get constraints for a pattern
pattern_with_constraints_t *get_pattern_constraints(pcre2_code **patterns)
{
    if (pattern_constraints_storage == NULL)
        return NULL;
    
    khint_t k = kh_get(pattern_constraints_map, pattern_constraints_storage, (void *)patterns);
    if (k == kh_end(pattern_constraints_storage))
        return NULL;
    
    return kh_value(pattern_constraints_storage, k);
}

// Forward declarations
static char *normalize_constraint_markers(const char *str);
static char *normalize_constraint_content(const char *str);
static char *normalize_field_string(const char *field_str);

// If successful, puts 2 patterns in the patterns array, the first one is the header, the second is the fields
// Else returns an array with the first element being NULL
//提取消息的模式：消息头+消息域
char *extract_message_pattern(const char *header_str, khash_t(field_table) * field_table, pcre2_code **patterns, int debug_file, const char *debug_file_name)
{
    int errornumber;
    size_t erroroffset;
    char header_pattern[128] = {0};
    char fields_pattern[1024] = {0};
    // Enhanced regex to tolerate spaces in <<...>> markers:
    // - Allows spaces around << and >>: << INTEGER >>, <<INTEGER >>, << INTEGER>>
    // - Allows spaces inside the marker content: << INTEGER : 0 - 65535 >>
    // Pattern breakdown:
    //   (.*) - text before marker (group 1)
    //   <<\s* - opening << with optional spaces
    //   (.*?) - content (non-greedy match, group 2)
    //   \s*>> - closing >> with optional spaces
    //   (.*) - text after marker (group 3)
    //   |(.+) - fallback: entire string if no marker found (group 4)
    // Note: We use non-greedy match (.*?) to stop at the first >>
    pcre2_code *replacer = pcre2_compile("(?:(.*)(?:<<\\s*(.*?)\\s*>>)(.*))|(.+)", PCRE2_ZERO_TERMINATED, PCRE2_DOTALL, &errornumber, &erroroffset, NULL);
    if (!replacer)
    {
        // Fallback to original pattern if compilation fails
        replacer = pcre2_compile("(?:(.*)(?:<<(.*)>>)(.*))|(.+)", PCRE2_ZERO_TERMINATED, PCRE2_DOTALL, &errornumber, &erroroffset, NULL);
    }
    pcre2_match_data *match_data = pcre2_match_data_create_from_pattern(replacer, NULL);
    char *message_type = NULL;
    
    // Arrays to store constraints
    type_constraint_t **header_constraints = NULL;
    int header_constraint_count = 0;
    type_constraint_t **field_constraints = NULL;
    int field_constraint_count = 0;
    int field_constraint_capacity = 0;
    
    // int offset = 0;
    /**
     * Example output
     * patterns[0] = (?:PLAY (.*)\r\n)
     * patterns[1] = (?|(?:CSeq: (.*)\r\n)|(?:User-Agent: (.*)\r\n)|(?:Range: (.*)\r\n)|(?:\r\n))
     */

    {
        // We use the string in such an escaped format for easier debugging as the regex library supports parsing it properly
        // The string contains quotations so they are ignored
        header_str++;

        int message_len = 0;
        while (header_str[message_len] != '\0' 
        && header_str[message_len] != ' ' 
        && header_str[message_len] != '\n' 
        && header_str[message_len] != '\r' 
        && header_str[message_len] != '\\' )
        {
            message_len++;
        }
        message_type = ck_alloc(message_len + 1);
        memcpy(message_type, header_str, message_len);
        message_type[message_len] = '\0';

        size_t len = strlen(header_str) - 1;
        strcat(header_pattern, "^"); // Ensure that it captures the start of the string
        
        // Normalize constraint markers in header string for robust parsing
        char *normalized_header = normalize_constraint_markers(header_str);
        const char *header_to_parse = normalized_header ? normalized_header : header_str;
        size_t header_parse_len = normalized_header ? strlen(normalized_header) : len;
        
        type_constraint_t *header_constraint = NULL;
        if (!parse_pattern(replacer, match_data, header_to_parse, header_parse_len, header_pattern, &header_constraint))
        {
            if (normalized_header) ck_free(normalized_header);
            patterns[0] = NULL;
            pcre2_match_data_free(match_data);
            pcre2_code_free(replacer);
            return NULL;
        }
        
        if (normalized_header) ck_free(normalized_header);
        
        // Store header constraint if found
        if (header_constraint && header_constraint->type != CONSTRAINT_NONE)
        {
            header_constraints = (type_constraint_t **)ck_alloc(sizeof(type_constraint_t *));
            header_constraints[0] = header_constraint;
            header_constraint_count = 1;
        }
        else if (header_constraint)
        {
            free_constraint(header_constraint);
        }
    }

    int first = 1;

    strcat(fields_pattern, "(?|");
    for (khiter_t field_t_iter = kh_begin(field_table); field_t_iter != kh_end(field_table); ++field_t_iter)
    {
        // Lower threshold: require only 2 occurrences (40% instead of 60%)
        // This allows more fields to pass the consistency check
        if (!kh_exist(field_table, field_t_iter) || kh_value(field_table, field_t_iter) < 2)
            continue;

        // Save current pattern state for fault tolerance
        size_t pattern_save_len = strlen(fields_pattern);
        
        // Add separator before attempting to parse
        if (!first)
        {
            strcat(fields_pattern, "|");
        }
        else
        {
            first = 0;
        }

        json_object *field_v = json_object_new_string(kh_key(field_table, field_t_iter));
        const char *str = json_object_to_json_string(field_v);
        // We use the string in such an escaped format for easier debugging as the regex library supports parsing it properly
        // The string contains quotations so they are ignored
        str++;
        size_t len = strlen(str) - 1;
        
        // Try to normalize the field string first to merge similar formats
        char *normalized_str = normalize_field_string(str);
        const char *str_to_parse = normalized_str ? normalized_str : str;
        size_t parse_len = normalized_str ? strlen(normalized_str) : len;
        
        type_constraint_t *field_constraint = NULL;
        int matched = parse_pattern(replacer, match_data, str_to_parse, parse_len, fields_pattern, &field_constraint);
        
        if (normalized_str) ck_free(normalized_str);
        json_object_put(field_v);
        
        // Fault-tolerant: restore pattern state if parsing fails, but continue with others
        if (!matched)
        {
            // Restore pattern to saved state
            fields_pattern[pattern_save_len] = '\0';
            // Restore first flag if this was the first field attempt
            if (pattern_save_len == 3) // Only "(?|" was there
            {
                first = 1;
            }
            if (field_constraint) free_constraint(field_constraint);
            continue;
        }
        
        // Store field constraint if found
        if (field_constraint && field_constraint->type != CONSTRAINT_NONE)
        {
            if (field_constraint_count >= field_constraint_capacity)
            {
                field_constraint_capacity = field_constraint_capacity == 0 ? 8 : field_constraint_capacity * 2;
                field_constraints = (type_constraint_t **)ck_realloc(field_constraints, field_constraint_capacity * sizeof(type_constraint_t *));
            }
            field_constraints[field_constraint_count++] = field_constraint;
        }
        else if (field_constraint)
        {
            free_constraint(field_constraint);
        }
    }

    strcat(fields_pattern, ")");

    if (first == 1)
    { // convert from (?|) to (.+) when the group is empty
        fields_pattern[1] = '.';
        fields_pattern[2] = '+';
    }

    pcre2_match_data_free(match_data);
    pcre2_code_free(replacer);
    printf("Header pattern is %s\n", header_pattern);
    printf("Fields pattern is %s\n", fields_pattern);

    if (debug_file != -1 && debug_file_name != NULL)
    {
        ck_write(debug_file, header_pattern, strlen(header_pattern), debug_file_name);
        ck_write(debug_file, "\n", 1, debug_file_name);
        ck_write(debug_file, fields_pattern, strlen(fields_pattern), debug_file_name);
    }

    {
        pcre2_code *p = pcre2_compile(header_pattern, PCRE2_ZERO_TERMINATED, 0, &errornumber, &erroroffset, NULL);
        pcre2_jit_compile(p, PCRE2_JIT_COMPLETE);
        patterns[0] = p;
    }
    {
        pcre2_code *p = pcre2_compile(fields_pattern, PCRE2_ZERO_TERMINATED, 0, &errornumber, &erroroffset, NULL);
        pcre2_jit_compile(p, PCRE2_JIT_COMPLETE);
        patterns[1] = p;
    }
    
    // Store constraints for this pattern
    if (header_constraint_count > 0 || field_constraint_count > 0)
    {
        store_pattern_constraints(patterns, header_constraints, header_constraint_count, 
                                  field_constraints, field_constraint_count);
    }
    else
    {
        // Free constraint arrays if no constraints found
        if (header_constraints) ck_free(header_constraints);
        if (field_constraints) ck_free(field_constraints);
    }
    
    return message_type;
}

range_list starts_with(char *line, int length, pcre2_code *pattern, pcre2_code **patterns_array)
{
    pcre2_match_data *match_data = pcre2_match_data_create_from_pattern(pattern, NULL);

    int rc = pcre2_match(pattern, line, length, 0, 0, match_data, NULL); // find the first range

    // Get constraints for this pattern if available
    pattern_with_constraints_t *pc = NULL;
    if (patterns_array)
    {
        pc = get_pattern_constraints(patterns_array);
    }

    // printf("starts_with rc is %d\n", rc);
    if (rc < 0)
    {
        switch (rc)
        {
        case PCRE2_ERROR_NOMATCH:
            // printf("No match!\n");
            break;
        default:
            // printf("Matching error %d\n", rc);
            break;
        }
        pcre2_match_data_free(match_data);
        range_list res;
        kv_init(res);
        return res;
    }

    range_list dyn_ranges;
    kv_init(dyn_ranges);
    PCRE2_SIZE *ovector = pcre2_get_ovector_pointer(match_data);
    for (int i = 1; i < rc; i++)
    {
        if (ovector[2 * i] == (PCRE2_SIZE)-1)
            continue;
        // printf("Group %d %d %d\n",i, ovector[2 * i], ovector[2 * i + 1]);
        range v = {.start = ovector[2 * i], .len = ovector[2 * i + 1] - ovector[2 * i], .mutable = 1, .constraint = NULL};
        
        // Associate constraint if available (header constraints for header pattern)
        if (pc && pc->header_constraints && i - 1 < pc->header_constraint_count)
        {
            // Duplicate constraint for this range
            type_constraint_t *constraint = pc->header_constraints[i - 1];
            if (constraint)
            {
                type_constraint_t *constraint_copy = (type_constraint_t *)ck_alloc(sizeof(type_constraint_t));
                memcpy(constraint_copy, constraint, sizeof(type_constraint_t));
                // For ENUM, we need to copy the values array
                if (constraint->type == CONSTRAINT_ENUM)
                {
                    constraint_copy->constraint.enum_values.values = (char **)ck_alloc(constraint->constraint.enum_values.count * sizeof(char *));
                    for (int j = 0; j < constraint->constraint.enum_values.count; j++)
                    {
                        constraint_copy->constraint.enum_values.values[j] = strdup(constraint->constraint.enum_values.values[j]);
                    }
                }
                v.constraint = constraint_copy;
            }
        }
        
        kv_push(range, dyn_ranges, v);
        // kv_push(range, dyn_ranges, v);
        //  ranges[0][i - 1] = v;
    }
    range v = {.start = ovector[0], .len = ovector[1] - ovector[0], .mutable = 1, .constraint = NULL};
    kv_push(range, dyn_ranges, v); // add the global range at the end

    pcre2_match_data_free(match_data);
    return dyn_ranges;
}

range_list get_mutable_ranges(char *line, int length, int offset, pcre2_code *pattern, pcre2_code **patterns_array)
{
    pcre2_match_data *match_data = pcre2_match_data_create_from_pattern(pattern, NULL);

    // Get constraints for this pattern if available
    pattern_with_constraints_t *pc = NULL;
    if (patterns_array)
    {
        pc = get_pattern_constraints(patterns_array);
    }

    range_list dyn_ranges;
    kv_init(dyn_ranges);
    int constraint_index = 0; // Track which field constraint to use

    for (;;) // catch all the other ranges
    {
        int rc = pcre2_match(pattern, line, length, offset, 0, match_data, NULL);
        if (rc < 0)
        {
            switch (rc)
            {
            case PCRE2_ERROR_NOMATCH:
                // printf("No match!\n");
                break;
            default:
                // printf("Matching error %d\n", rc);
                break;
            }
            pcre2_match_data_free(match_data);
            match_data = NULL;
            break;
        }
        PCRE2_SIZE *ovector = pcre2_get_ovector_pointer(match_data);
        if (offset != ovector[0])
        {
            range v = {.start = offset, .len = ovector[0] - offset, .mutable = 1, .constraint = NULL};
            kv_push(range, dyn_ranges, v);
        }

        // printf("Matched over %d %d\n", ovector[0], ovector[1]);
        for (int i = 1; i < rc; i++)
        {
            if (ovector[2 * i] == (PCRE2_SIZE)-1)
                continue;
            // printf("Group %d %d %d\n",i, ovector[2 * i], ovector[2 * i + 1]);
            range v = {.start = ovector[2 * i], .len = ovector[2 * i + 1] - ovector[2 * i], .mutable = 1, .constraint = NULL};
            
            // Associate constraint if available (field constraints for fields pattern)
            if (pc && pc->field_constraints && constraint_index < pc->field_constraint_count)
            {
                type_constraint_t *constraint = pc->field_constraints[constraint_index];
                if (constraint)
                {
                    type_constraint_t *constraint_copy = (type_constraint_t *)ck_alloc(sizeof(type_constraint_t));
                    memcpy(constraint_copy, constraint, sizeof(type_constraint_t));
                    // For ENUM, we need to copy the values array
                    if (constraint->type == CONSTRAINT_ENUM)
                    {
                        constraint_copy->constraint.enum_values.values = (char **)ck_alloc(constraint->constraint.enum_values.count * sizeof(char *));
                        for (int j = 0; j < constraint->constraint.enum_values.count; j++)
                        {
                            constraint_copy->constraint.enum_values.values[j] = strdup(constraint->constraint.enum_values.values[j]);
                        }
                    }
                    v.constraint = constraint_copy;
                }
                constraint_index++;
            }
            
            kv_push(range, dyn_ranges, v);
            // ranges[0][i - 1] = v;
        }
        if (offset == ovector[1])
        { // in the case the match is empty, we just move a step forward
            offset++;
        }
        else
        {
            offset = ovector[1];
        }
    }

    if (offset < length) // catch anything past the last matched pattern
    {
        range v = {.start = offset, .len = length - offset, .mutable = 1, .constraint = NULL};
        kv_push(range, dyn_ranges, v);
    }

    if (match_data != NULL)
    {
        pcre2_match_data_free(match_data);
    }
    return dyn_ranges;
}

char *unescape_string(const char *input)
{
    size_t length = strlen(input);
    char *output = (char *)malloc((length + 1) * sizeof(char));

    if (output == NULL)
    {
        printf("Memory allocation failed.\n");
        return NULL;
    }

    size_t i, j = 0;
    for (i = 0; i < length; i++)
    {
        if (input[i] == '\\')
        {
            i++; // Skip the backslash
            switch (input[i])
            {
            case 'n':
                output[j++] = '\n';
                break;
            case 't':
                output[j++] = '\t';
                break;
            case 'r':
                output[j++] = '\r';
                break;
            case '\\':
                output[j++] = '\\';
                break;
            default:
                output[j++] = input[i];
                break;
            }
        }
        else
        {
            output[j++] = input[i];
        }
    }

    output[j] = '\0'; // Add null-terminator to the output string
    return output;
}

// Normalize <<...>> constraint markers: remove spaces inside and around markers
// Handles cases like "<< INTEGER >>", "<<INTEGER >>", "<< INTEGER>>" -> "<<INTEGER>>"
static char *normalize_constraint_markers(const char *str)
{
    if (!str) return NULL;
    
    size_t len = strlen(str);
    char *normalized = (char *)ck_alloc(len * 2 + 1); // Allocate extra space for worst case
    if (!normalized) return NULL;
    
    int i = 0, j = 0;
    int in_marker = 0; // Track if we're inside <<...>>
    int marker_start = -1; // Position where << started
    
    while (i < len)
    {
        // Detect start of constraint marker <<
        if (i < len - 1 && str[i] == '<' && str[i + 1] == '<')
        {
            normalized[j++] = '<';
            normalized[j++] = '<';
            i += 2;
            in_marker = 1;
            marker_start = j;
            
            // Skip whitespace immediately after <<
            while (i < len && (str[i] == ' ' || str[i] == '\t'))
                i++;
            continue;
        }
        
        // Detect end of constraint marker >>
        if (in_marker && i < len - 1 && str[i] == '>' && str[i + 1] == '>')
        {
            // Remove trailing spaces before >>
            while (j > marker_start && (normalized[j-1] == ' ' || normalized[j-1] == '\t'))
                j--;
            
            normalized[j++] = '>';
            normalized[j++] = '>';
            i += 2;
            in_marker = 0;
            marker_start = -1;
            continue;
        }
        
        // Inside marker: collapse spaces to single space, but preserve structure
        if (in_marker)
        {
            if (str[i] == ' ' || str[i] == '\t')
            {
                // Only add space if previous char wasn't space and wasn't <<
                if (j > marker_start + 1 && normalized[j-1] != ' ' && normalized[j-1] != '\t')
                {
                    normalized[j++] = ' ';
                }
                i++;
            }
            else
            {
                normalized[j++] = str[i++];
            }
        }
        else
        {
            // Outside marker: copy as-is
            normalized[j++] = str[i++];
        }
    }
    
    normalized[j] = '\0';
    return normalized;
}

// Normalize field string format: remove extra spaces, standardize format
// This helps merge similar field formats that differ only in whitespace
// Now also handles <<...>> constraint markers robustly
static char *normalize_field_string(const char *field_str)
{
    if (!field_str) return NULL;
    
    // First normalize constraint markers <<...>>
    char *marker_normalized = normalize_constraint_markers(field_str);
    if (!marker_normalized) return NULL;
    
    size_t len = strlen(marker_normalized);
    char *normalized = (char *)ck_alloc(len + 1);
    if (!normalized)
    {
        ck_free(marker_normalized);
        return NULL;
    }
    
    int i = 0, j = 0;
    int last_was_space = 0;
    
    // Remove leading whitespace
    while (i < len && (marker_normalized[i] == ' ' || marker_normalized[i] == '\t'))
        i++;
    
    // Normalize: collapse multiple spaces to single space
    // But preserve spaces inside <<...>> markers
    int in_marker = 0;
    while (i < len)
    {
        // Track if we're inside a constraint marker
        if (i < len - 1 && marker_normalized[i] == '<' && marker_normalized[i + 1] == '<')
        {
            in_marker = 1;
        }
        else if (i < len - 1 && marker_normalized[i] == '>' && marker_normalized[i + 1] == '>')
        {
            in_marker = 0;
        }
        
        if (marker_normalized[i] == ' ' || marker_normalized[i] == '\t')
        {
            // Inside markers, preserve single spaces; outside, collapse
            if (in_marker)
            {
                // Only add space if previous char wasn't space
                if (j > 0 && normalized[j-1] != ' ' && normalized[j-1] != '\t')
                {
                    normalized[j++] = ' ';
                    last_was_space = 1;
                }
            }
            else
            {
                // Outside markers: collapse spaces
                if (!last_was_space && j > 0 && normalized[j-1] != '\r' && normalized[j-1] != '\n')
                {
                    normalized[j++] = ' ';
                    last_was_space = 1;
                }
            }
        }
        else
        {
            normalized[j++] = marker_normalized[i];
            last_was_space = 0;
        }
        i++;
    }
    
    // Remove trailing whitespace
    while (j > 0 && (normalized[j-1] == ' ' || normalized[j-1] == '\t'))
        j--;
    
    normalized[j] = '\0';
    ck_free(marker_normalized);
    return normalized;
}

void write_new_seeds(char *enriched_file, char *contents)
{
    FILE *fp = fopen(enriched_file, "w");
    if (fp == NULL)
    {
        printf("Error in opening the file %s\n", enriched_file);
        exit(1);
    }

    // remove the newline and whiltespace in the beginning of the string if any
    while (contents[0] == '\n' || contents[0] == ' ' || contents[0] == '\t' || contents[0] == '\r')
    {
        contents++;
    }

    // Check if last 4 characters of the client_request_answer string are \r\n\r\n
    // If not, add them
    int len = strlen(contents);
    if (contents[len - 1] != '\n' || contents[len - 2] != '\r' || contents[len - 3] != '\n' || contents[len - 4] != '\r')
    {
        fprintf(fp, "%s\r\n\r\n", contents);
    }
    else
    {
        fprintf(fp, "%s", contents);
    }

    fclose(fp);
}

char *format_string(char *state_string)
{
    // remove the newline and whiltespace in the beginning of the string if any
    while (state_string[0] == '\n' || state_string[0] == ' ' || state_string[0] == '\t' || state_string[0] == '\r')
    {
        state_string++;
    }

    int len = strlen(state_string);
    while (state_string[len - 1] == '\n' || state_string[len - 1] == '\r' || state_string[len - 1] == ' ' || state_string[len - 1] == '.')
    {
        state_string[len - 1] = '\0';
        len--;
    }

    return state_string;
}

/***
 * Get the protocol states based on self-consistency check
 * pass the parameters: protocol_name, states_set, states_string
 ***/
void get_protocol_message_types(char *state_prompt, khash_t(strSet) * states_set)
{
    khash_t(strMap) *state_to_times = kh_init(strMap); // map from state to times

    char *full_prompt = NULL;
    asprintf(&full_prompt, "%s", state_prompt);

    for (int i = 0; i < CONFIDENT_TIMES; i++)
    {
        char *state_answer = chat_with_llm(full_prompt, "instruct", MESSAGE_TYPE_RETRIES, 0.5);
        if (state_answer == NULL)
            continue;

        state_answer = format_string(state_answer);

        char *state_tokens = strtok(state_answer, ",");
        while (state_tokens != NULL)
        {
            char *protocol_state = state_tokens;
            protocol_state = format_string(protocol_state);

            int ret;
            khiter_t k = kh_put(strMap, state_to_times, protocol_state, &ret);
            if (ret == 0)
            {
                kh_value(state_to_times, k)++;
            }
            else
            {
                kh_value(state_to_times, k) = 1;
            }

            state_tokens = strtok(NULL, ",");
        }
    }

    for (khiter_t k = kh_begin(state_to_times); k != kh_end(state_to_times); ++k)
    {
        if (kh_exist(state_to_times, k))
        {
            if (kh_value(state_to_times, k) >= 0.5 * CONFIDENT_TIMES)
            {
                const char *protocol_state = kh_key(state_to_times, k);

                int ret;
                kh_put(strSet, states_set, protocol_state, &ret);
            }
        }
    }

    free(full_prompt);
}

khash_t(strSet) * duplicate_hash(khash_t(strSet) * set)
{
    khash_t(strSet) *new_set = kh_init(strSet);

    for (khiter_t k = kh_begin(set); k != kh_end(set); ++k)
    {
        if (kh_exist(set, k))
        {
            const char *val = kh_key(set, k);
            int ret;
            kh_put(strSet, new_set, val, &ret);
        }
    }

    return new_set;
}

void make_combination(khash_t(strSet)* sequence, const char** data , message_set_list* res,khiter_t st, khiter_t end, int index, int size);

message_set_list message_combinations(khash_t(strSet)* sequence, int size)
{
    message_set_list res;
    kv_init(res);
    const char* data[size];
    make_combination(sequence, data, &res, kh_begin(sequence), kh_end(sequence), 0, size);
    return res;
}

void make_combination(khash_t(strSet)* sequence, const char** data, message_set_list* res, khiter_t st, khiter_t end,
                     int index, int size)
{

    if (index == size)
    {
        khash_t(strSet)* combination = kh_init(strSet);
        int absent;
        for (int j=0; j<size; j++){
            kh_put(strSet, combination, data[j], &absent);
        }
        kv_push(khash_t(strSet)*, *res, combination);
        return;
    }
    for (khiter_t i=st; i != end && end-i+1 >= size-index; i++)
    {
        if(!kh_exist(sequence,i))
            continue;
        data[index] = kh_key(sequence,i);
        make_combination(sequence, data, res, i+1, end, index+1, size);
    }
}



int min(int a, int b) {
    return a < b ? a : b;
}

// Extract pure sequence from LLM response (remove explanations, markdown, etc.)
static char *extract_sequence_from_response(const char *response) {
    if (!response) return NULL;
    
    // Try to find code blocks first (```)
    const char *code_start = strstr(response, "```");
    if (code_start) {
        code_start += 3; // Skip ```
        // Skip language identifier if present
        while (*code_start == '\n' || *code_start == ' ' || 
               (*code_start >= 'a' && *code_start <= 'z') ||
               (*code_start >= 'A' && *code_start <= 'Z')) {
            code_start++;
        }
        const char *code_end = strstr(code_start, "```");
        if (code_end) {
            int len = code_end - code_start;
            char *result = malloc(len + 1);
            strncpy(result, code_start, len);
            result[len] = '\0';
            return result;
        }
    }
    
    // Try to find sequence between "Modified sequence:" or similar markers
    const char *markers[] = {
        "Modified sequence:",
        "modified sequence:",
        "Sequence:",
        "sequence:",
        "Output:",
        "output:"
    };
    
    for (int i = 0; i < sizeof(markers) / sizeof(markers[0]); i++) {
        const char *marker = strstr(response, markers[i]);
        if (marker) {
            marker += strlen(markers[i]);
            // Skip whitespace and newlines
            while (*marker == ' ' || *marker == '\n' || *marker == '\r' || *marker == '\t') {
                marker++;
            }
            
            // Find the end (either end of string or next section)
            const char *end = marker;
            while (*end != '\0' && 
                   !(end[0] == '\n' && (strstr(end, "Note:") || strstr(end, "---") || strstr(end, "**")))) {
                end++;
            }
            
            int len = end - marker;
            if (len > 0) {
                char *result = malloc(len + 1);
                strncpy(result, marker, len);
                result[len] = '\0';
                return result;
            }
        }
    }
    
    // If no markers found, try to extract lines that look like commands
    // (lines that start with uppercase letters, possibly with parameters)
    char *result = malloc(strlen(response) + 1);
    char *out = result;
    const char *in = response;
    int in_command_block = 0;
    
    while (*in) {
        // Look for patterns like "USER", "PASS", "CWD", etc. at start of line
        if ((*in == '\n' || in == response) && 
            ((in[1] >= 'A' && in[1] <= 'Z') || 
             (in[1] >= 'a' && in[1] <= 'z'))) {
            in_command_block = 1;
        }
        
        if (in_command_block) {
            if (*in == '\n' && 
                !((in[1] >= 'A' && in[1] <= 'Z') || 
                  (in[1] >= 'a' && in[1] <= 'z') ||
                  (in[1] == ' ' || in[1] == '\t') ||
                  (in[1] == '\0'))) {
                // End of command block
                break;
            }
            *out++ = *in;
        }
        in++;
    }
    *out = '\0';
    
    // If we extracted something meaningful, return it
    if (strlen(result) > 10) {
        return result;
    }
    
    free(result);
    // Last resort: return original response
    return strdup(response);
}

char *enrich_sequence(char *sequence, khash_t(strSet) * missing_message_types)
{
    const char *prompt_template =
        "CRITICAL: Return ONLY the modified sequence, NO explanations, NO analysis, NO markdown.\\n\\n"
        "Original sequence:\\n"
        "%.*s\\n\\n"
        "Task: Add these message types: %.*s\\n"
        "Insert them at appropriate locations.\\n\\n"
        "Output format: Return ONLY the sequence, one command per line, like this:\\n"
        "```\\n"
        "USER username\\n"
        "PASS password\\n"
        "CWD /path\\n"
        "QUIT\\n"
        "```\\n\\n"
        "Modified sequence:";

    int missing_fields_len = 0;
    int missing_fields_capacity = 100;
    char *missing_fields_seq = ck_alloc(missing_fields_capacity);

    khiter_t k;
    int i = 0;
    for (k = kh_begin(missing_message_types); 
    k != kh_end(missing_message_types) && i < min(MAX_ENRICHMENT_MESSAGE_TYPES, kh_size(missing_message_types)); 
    ++k)
    {
        if (!kh_exist(missing_message_types, k))
            continue;
        ++i; // Increment only after seeing a message type
        const char *message_type = kh_key(missing_message_types, k);
        int needed_len = strlen(message_type) + 2; // add for the ', '

        if (missing_fields_len + needed_len > missing_fields_capacity)
        {
            missing_fields_capacity += 2 * needed_len;
            missing_fields_seq = ck_realloc(missing_fields_seq, missing_fields_capacity);
        }

        memcpy(missing_fields_seq + missing_fields_len, message_type, strlen(message_type));
        memcpy(missing_fields_seq + missing_fields_len + needed_len - 2, ", ", 2);

        missing_fields_len += needed_len;
    }
    missing_fields_len -= 2; // ignore the last ', '

    char *prompt = NULL;

    json_object *sequence_escaped = json_object_new_string(sequence);
    const char *sequence_escaped_str = json_object_to_json_string(sequence_escaped);
    sequence_escaped_str++;

    int sequence_len = strlen(sequence_escaped_str) - 1;
    int allowed_tokens = (MAX_TOKENS - strlen(prompt_template) - missing_fields_len);
    if (sequence_len > allowed_tokens)
    {
        sequence_len = allowed_tokens;
    }
    asprintf(&prompt, prompt_template, sequence_len, sequence_escaped_str, missing_fields_len, missing_fields_seq);
    ck_free(missing_fields_seq);
    json_object_put(sequence_escaped);

    char *response = chat_with_llm(prompt, "instruct", ENRICHMENT_RETRIES, 0.5);

    free(prompt);

    if (response == NULL) {
        return NULL;
    }

    // Extract pure sequence from response (remove explanations, markdown, etc.)
    char *clean_response = extract_sequence_from_response(response);
    free(response);
    
    if (clean_response == NULL) {
        return NULL;
    }
    
    // Remove markdown code block markers if still present
    char *cleaned = clean_response;
    if (cleaned[0] == '`' && cleaned[1] == '`' && cleaned[2] == '`') {
        cleaned += 3;
        // Skip language identifier
        while (*cleaned == '\n' || *cleaned == ' ' || 
               (*cleaned >= 'a' && *cleaned <= 'z') ||
               (*cleaned >= 'A' && *cleaned <= 'Z')) {
            cleaned++;
        }
        // Remove trailing ```
        char *end = strstr(cleaned, "```");
        if (end) {
            *end = '\0';
        }
    }
    
    // Trim whitespace
    while (*cleaned == ' ' || *cleaned == '\n' || *cleaned == '\r' || *cleaned == '\t') {
        cleaned++;
    }
    char *end = cleaned + strlen(cleaned) - 1;
    while (end > cleaned && (*end == ' ' || *end == '\n' || *end == '\r' || *end == '\t')) {
        *end = '\0';
        end--;
    }
    
    // If we modified the pointer, need to create new string
    if (cleaned != clean_response) {
        char *result = strdup(cleaned);
        free(clean_response);
        return result;
    }
    
    return clean_response;
}

// Parse constraint from string like "<<INTEGER:0-65535>>" or "<<ENUM:GET,POST>>"
type_constraint_t *parse_constraint(const char *str)
{
    if (!str || str[0] != '<' || str[1] != '<')
        return NULL;
    
    type_constraint_t *constraint = (type_constraint_t *)ck_alloc(sizeof(type_constraint_t));
    constraint->type = CONSTRAINT_NONE;
    
    // Skip "<<"
    const char *start = str + 2;
    const char *end = strstr(start, ">>");
    if (!end)
    {
        constraint->type = CONSTRAINT_NONE;
        return constraint;
    }
    
    size_t len = end - start;
    char *constraint_str = (char *)ck_alloc(len + 1);
    strncpy(constraint_str, start, len);
    constraint_str[len] = '\0';
    
    // Check for VALUE (no constraint)
    if (strncmp(constraint_str, "VALUE", 5) == 0)
    {
        constraint->type = CONSTRAINT_NONE;
        ck_free(constraint_str);
        return constraint;
    }
    
    // Check for INTEGER:min-max
    if (strncmp(constraint_str, "INTEGER:", 8) == 0)
    {
        constraint->type = CONSTRAINT_INTEGER;
        const char *range = constraint_str + 8;
        char *dash = strchr(range, '-');
        if (dash)
        {
            constraint->constraint.integer_range.min = atoi(range);
            constraint->constraint.integer_range.max = atoi(dash + 1);
        }
        else
        {
            // No range specified, use default
            constraint->constraint.integer_range.min = 0;
            constraint->constraint.integer_range.max = 65535;
        }
        ck_free(constraint_str);
        return constraint;
    }
    
    // Check for STRING:min-max
    if (strncmp(constraint_str, "STRING:", 7) == 0)
    {
        constraint->type = CONSTRAINT_STRING;
        const char *range = constraint_str + 7;
        char *dash = strchr(range, '-');
        if (dash)
        {
            constraint->constraint.string_range.min_len = atoi(range);
            constraint->constraint.string_range.max_len = atoi(dash + 1);
        }
        else
        {
            constraint->constraint.string_range.min_len = 1;
            constraint->constraint.string_range.max_len = 256;
        }
        ck_free(constraint_str);
        return constraint;
    }
    
    // Check for ENUM:val1,val2,val3
    if (strncmp(constraint_str, "ENUM:", 5) == 0)
    {
        constraint->type = CONSTRAINT_ENUM;
        const char *values = constraint_str + 5;
        
        // Count commas to determine number of values
        int count = 1;
        const char *p = values;
        while (*p)
        {
            if (*p == ',') count++;
            p++;
        }
        
        constraint->constraint.enum_values.count = count;
        constraint->constraint.enum_values.values = (char **)ck_alloc(count * sizeof(char *));
        
        // Parse values
        char *values_copy = strdup(values);
        char *token = strtok(values_copy, ",");
        int i = 0;
        while (token && i < count)
        {
            // Trim whitespace
            while (*token == ' ') token++;
            char *end_token = token + strlen(token) - 1;
            while (end_token > token && *end_token == ' ') *end_token-- = '\0';
            
            constraint->constraint.enum_values.values[i] = strdup(token);
            token = strtok(NULL, ",");
            i++;
        }
        free(values_copy);
        ck_free(constraint_str);
        return constraint;
    }
    
    // Check for IP
    if (strcmp(constraint_str, "IP") == 0)
    {
        constraint->type = CONSTRAINT_IP;
        ck_free(constraint_str);
        return constraint;
    }
    
    // Check for PATH
    if (strcmp(constraint_str, "PATH") == 0)
    {
        constraint->type = CONSTRAINT_PATH;
        ck_free(constraint_str);
        return constraint;
    }
    
    // Check for HEX
    if (strcmp(constraint_str, "HEX") == 0)
    {
        constraint->type = CONSTRAINT_HEX;
        ck_free(constraint_str);
        return constraint;
    }
    
    // Unknown constraint type, treat as VALUE
    constraint->type = CONSTRAINT_NONE;
    ck_free(constraint_str);
    return constraint;
}

    // Free constraint memory
void free_constraint(type_constraint_t *constraint)
{
    if (!constraint)
        return;
    
    if (constraint->type == CONSTRAINT_ENUM)
    {
        for (int i = 0; i < constraint->constraint.enum_values.count; i++)
        {
            if (constraint->constraint.enum_values.values[i])
                free(constraint->constraint.enum_values.values[i]);
        }
        ck_free(constraint->constraint.enum_values.values);
    }
    
    ck_free(constraint);
}

// Generate a value according to the constraint
char *generate_value_by_constraint(type_constraint_t *constraint)
{
    // Control mutation magnitude: ensure a certain percentage of "minimal mutations"
    // (only mutate content, not length) to maintain network interaction stability
    // This prevents socket buffer overflow or timeout issues that could mask logic bugs
    // Use 30% probability for minimal mutation (configurable via random() % 100 < 30)
    const int MINIMAL_MUTATION_PROBABILITY = 30; // 30% chance for minimal mutation
    int is_minimal_mutation = (random() % 100) < MINIMAL_MUTATION_PROBABILITY;
    
    if (!constraint || constraint->type == CONSTRAINT_NONE)
    {
        // Generate a random string
        int len;
        if (is_minimal_mutation)
        {
            // Minimal mutation: use fixed small length to avoid socket buffer issues
            len = 10; // Fixed small length, only mutate content
        }
        else
        {
            // Normal mutation: allow length variation
            len = 10 + (random() % 20);
        }
        char *value = (char *)ck_alloc(len + 1);
        for (int i = 0; i < len; i++)
        {
            value[i] = 32 + (random() % 95); // Printable ASCII
        }
        value[len] = '\0';
        return value;
    }
    
    switch (constraint->type)
    {
        case CONSTRAINT_INTEGER:
        {
            int min = constraint->constraint.integer_range.min;
            int max = constraint->constraint.integer_range.max;
            int value = min + (random() % (max - min + 1));
            char *str = (char *)ck_alloc(32);
            snprintf(str, 32, "%d", value);
            return str;
        }
        
        case CONSTRAINT_STRING:
        {
            int min_len = constraint->constraint.string_range.min_len;
            int max_len = constraint->constraint.string_range.max_len;
            int len;
            if (is_minimal_mutation)
            {
                // Minimal mutation: use minimum length, only mutate content
                len = min_len;
            }
            else
            {
                // Normal mutation: allow length variation within range
                len = min_len + (random() % (max_len - min_len + 1));
            }
            char *value = (char *)ck_alloc(len + 1);
            for (int i = 0; i < len; i++)
            {
                value[i] = 32 + (random() % 95); // Printable ASCII
            }
            value[len] = '\0';
            return value;
        }
        
        case CONSTRAINT_ENUM:
        {
            int count = constraint->constraint.enum_values.count;
            if (count > 0)
            {
                int idx = random() % count;
                return strdup(constraint->constraint.enum_values.values[idx]);
            }
            return strdup("");
        }
        
        case CONSTRAINT_IP:
        {
            char *ip = (char *)ck_alloc(16);
            snprintf(ip, 16, "%d.%d.%d.%d", 
                     (int)(random() % 256), (int)(random() % 256), 
                     (int)(random() % 256), (int)(random() % 256));
            return ip;
        }
        
        case CONSTRAINT_PATH:
        {
            const char *path_prefixes[] = {"/", "/tmp/", "/var/", "/usr/", "/home/"};
            const char *path_suffixes[] = {"file", "test", "data", "config", "log"};
            int prefix_idx = random() % (sizeof(path_prefixes) / sizeof(path_prefixes[0]));
            int suffix_idx = random() % (sizeof(path_suffixes) / sizeof(path_suffixes[0]));
            int num = random() % 1000;
            char *path = (char *)ck_alloc(256);
            snprintf(path, 256, "%s%s%d", path_prefixes[prefix_idx], path_suffixes[suffix_idx], num);
            return path;
        }
        
        case CONSTRAINT_HEX:
        {
            int len;
            if (is_minimal_mutation)
            {
                // Minimal mutation: use fixed small length
                len = 4; // Fixed small length, only mutate content
            }
            else
            {
                // Normal mutation: allow length variation
                len = 4 + (random() % 20);
            }
            char *hex = (char *)ck_alloc(len + 1);
            const char *hex_chars = "0123456789ABCDEFabcdef";
            for (int i = 0; i < len; i++)
            {
                hex[i] = hex_chars[random() % 22];
            }
            hex[len] = '\0';
            return hex;
        }
        
        default:
        {
            char *value = (char *)ck_alloc(16);
            snprintf(value, 16, "value%d", (int)(random() % 10000));
            return value;
        }
    }
}

// ============================================================================
// Multi-Armed Bandit (MAB) Implementation for Mutation Operator Selection
// ============================================================================

// Global MAB instances for different constraint types
// These are initialized on first use
static multi_armed_bandit_t *mab_integer = NULL;  // 25+ operators for INTEGER
static multi_armed_bandit_t *mab_string = NULL;   // 20+ operators for STRING
static multi_armed_bandit_t *mab_enum = NULL;     // 8 operators for ENUM
static multi_armed_bandit_t *mab_ip = NULL;       // 15 operators for IP
static multi_armed_bandit_t *mab_path = NULL;      // 15 operators for PATH
static multi_armed_bandit_t *mab_hex = NULL;      // 12 operators for HEX

// Track last selected operator for feedback update
static constraint_type_t last_constraint_type = CONSTRAINT_NONE;
static u32 last_selected_operator = 0;
static u8 mab_enabled = 0;  // Global flag to enable/disable MAB

// Enable or disable MAB for mutation operator selection
void set_mab_enabled(u8 enabled)
{
    mab_enabled = enabled;
}

// Initialize a Multi-Armed Bandit with specified number of arms
multi_armed_bandit_t *mab_init(u32 num_arms)
{
    multi_armed_bandit_t *mab = (multi_armed_bandit_t *)ck_alloc(sizeof(multi_armed_bandit_t));
    if (!mab)
        return NULL;
    
    mab->arms = (mab_arm_t *)ck_alloc(num_arms * sizeof(mab_arm_t));
    if (!mab->arms)
    {
        ck_free(mab);
        return NULL;
    }
    
    // Initialize all arms
    for (u32 i = 0; i < num_arms; i++)
    {
        mab->arms[i].pulls = 0;
        mab->arms[i].rewards = 0;
        mab->arms[i].avg_reward = 0.0;
        mab->arms[i].ucb_value = 0.0;
    }
    
    mab->num_arms = num_arms;
    mab->total_pulls = 0;
    
    return mab;
}

// Free a Multi-Armed Bandit
void mab_free(multi_armed_bandit_t *mab)
{
    if (mab)
    {
        if (mab->arms)
            ck_free(mab->arms);
        ck_free(mab);
    }
}

// Select an arm using UCB1 algorithm
// Returns the index of the selected arm
u32 mab_select_arm(multi_armed_bandit_t *mab)
{
    if (!mab || mab->num_arms == 0)
        return 0;
    
    u32 selected_arm = 0;
    double max_ucb = -1.0;
    
    // UCB1 formula: argmax_i [avg_reward_i + sqrt(2 * ln(total_pulls) / pulls_i)]
    for (u32 i = 0; i < mab->num_arms; i++)
    {
        if (mab->arms[i].pulls == 0)
        {
            // If an arm hasn't been pulled, select it (exploration)
            return i;
        }
        
        // Calculate UCB1 value
        double exploration_bonus = sqrt(2.0 * log(mab->total_pulls + 1) / mab->arms[i].pulls);
        mab->arms[i].ucb_value = mab->arms[i].avg_reward + exploration_bonus;
        
        if (mab->arms[i].ucb_value > max_ucb)
        {
            max_ucb = mab->arms[i].ucb_value;
            selected_arm = i;
        }
    }
    
    return selected_arm;
}

// Update reward for a selected arm
// reward: 1 if new coverage found, 0 otherwise
void mab_update_reward(multi_armed_bandit_t *mab, u32 arm_index, u32 reward)
{
    if (!mab || arm_index >= mab->num_arms)
        return;
    
    mab_arm_t *arm = &mab->arms[arm_index];
    
    // Update statistics
    arm->pulls++;
    arm->rewards += reward;
    arm->avg_reward = (double)arm->rewards / arm->pulls;
    mab->total_pulls++;
}

// Get or initialize MAB for a constraint type
static multi_armed_bandit_t *get_mab_for_constraint(constraint_type_t type)
{
    switch (type)
    {
        case CONSTRAINT_INTEGER:
            if (!mab_integer)
                mab_integer = mab_init(25); // 25 mutation operators
            return mab_integer;
            
        case CONSTRAINT_STRING:
            if (!mab_string)
                mab_string = mab_init(20); // 20 mutation operators
            return mab_string;
            
        case CONSTRAINT_ENUM:
            if (!mab_enum)
                mab_enum = mab_init(8); // 8 mutation operators
            return mab_enum;
            
        case CONSTRAINT_IP:
            if (!mab_ip)
                mab_ip = mab_init(15); // 15 mutation operators
            return mab_ip;
            
        case CONSTRAINT_PATH:
            if (!mab_path)
                mab_path = mab_init(15); // 15 mutation operators
            return mab_path;
            
        case CONSTRAINT_HEX:
            if (!mab_hex)
                mab_hex = mab_init(12); // 12 mutation operators
            return mab_hex;
            
        default:
            return NULL;
    }
}

// Update reward for the last mutation operator used
// Call this function after checking if new coverage was found
// reward: 1 if new coverage found, 0 otherwise
void mab_update_last_mutation_reward(u32 reward)
{
    // Only update if MAB is enabled
    if (!mab_enabled)
        return;
    
    multi_armed_bandit_t *mab = NULL;
    
    switch (last_constraint_type)
    {
        case CONSTRAINT_INTEGER:
            mab = mab_integer;
            break;
        case CONSTRAINT_STRING:
            mab = mab_string;
            break;
        case CONSTRAINT_ENUM:
            mab = mab_enum;
            break;
        case CONSTRAINT_IP:
            mab = mab_ip;
            break;
        case CONSTRAINT_PATH:
            mab = mab_path;
            break;
        case CONSTRAINT_HEX:
            mab = mab_hex;
            break;
        default:
            return;
    }
    
    if (mab)
    {
        mab_update_reward(mab, last_selected_operator, reward);
    }
}

// Helper functions for format detection
static int is_email_format(const u8 *buf, u32 len)
{
    if (len < 5) return 0;
    const char *p = (const char *)buf;
    int has_at = 0, has_dot = 0;
    for (u32 i = 0; i < len && p[i] != '\0'; i++)
    {
        if (p[i] == '@') has_at = 1;
        if (has_at && p[i] == '.') has_dot = 1;
    }
    return has_at && has_dot;
}

static int is_url_format(const u8 *buf, u32 len)
{
    if (len < 7) return 0;
    const char *p = (const char *)buf;
    return (strncmp(p, "http://", 7) == 0 || strncmp(p, "https://", 8) == 0 ||
            strncmp(p, "ftp://", 6) == 0 || strncmp(p, "file://", 7) == 0);
}

static int is_base64_format(const u8 *buf, u32 len)
{
    if (len < 4) return 0;
    const char *p = (const char *)buf;
    int valid_chars = 0;
    for (u32 i = 0; i < len && p[i] != '\0'; i++)
    {
        char c = p[i];
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || 
            (c >= '0' && c <= '9') || c == '+' || c == '/' || c == '=')
            valid_chars++;
        else if (c != ' ' && c != '\n' && c != '\r')
            return 0;
    }
    return valid_chars > len * 0.7; // At least 70% valid base64 chars
}

// Mutate a value according to the constraint
void mutate_value_by_constraint(u8 *buf, u32 len, type_constraint_t *constraint, u32 offset)
{
    if (!constraint || constraint->type == CONSTRAINT_NONE || offset >= len)
        return;
    
    u32 available_len = len - offset;
    if (available_len == 0)
        return;
    
    switch (constraint->type)
    {
        case CONSTRAINT_INTEGER:
        {
            // Try to parse as integer and mutate
            char *str = (char *)ck_alloc(available_len + 1);
            memcpy(str, buf + offset, available_len);
            str[available_len] = '\0';
            
            int value = atoi(str);
            int min = constraint->constraint.integer_range.min;
            int max = constraint->constraint.integer_range.max;
            
            // Use Multi-Armed Bandit to select mutation operator
            multi_armed_bandit_t *mab = NULL;
            int mutation_type = 0;
            if (mab_enabled && (mab = get_mab_for_constraint(CONSTRAINT_INTEGER)))
            {
                mutation_type = (int)mab_select_arm(mab);
                last_constraint_type = CONSTRAINT_INTEGER;
                last_selected_operator = mutation_type;
            }
            else
            {
                // Fallback to random if MAB not enabled or not available
                mutation_type = (int)(random() % 25);
            }
            switch (mutation_type)
            {
                case 0: value += (random() % 10) - 5; break; // Small change
                case 1: value = min; break; // Min boundary
                case 2: value = max; break; // Max boundary
                case 3: value = min + (random() % (max - min + 1)); break; // Random in range
                case 4: value = min + 1; break; // Min + 1 (boundary+1)
                case 5: value = max - 1; break; // Max - 1 (boundary-1)
                case 6: value = (min + max) / 2; break; // Midpoint
                case 7: value = min - 1; break; // Underflow test
                case 8: value = max + 1; break; // Overflow test
                case 9: value = 0; break; // Zero
                case 10: value = -1; break; // Negative one
                case 11: value = 1; break; // One
                case 12: value = 2; break; // Two
                case 13: value = 10; break; // Ten
                case 14: value = 100; break; // Hundred
                case 15: value = 1000; break; // Thousand
                case 16: value = value * 2; break; // Double
                case 17: value = value / 2; break; // Half
                case 18: value = value * 10; break; // 10x
                case 19: value = value + value; break; // Self-add
                case 20: 
                    {
                        long long squared = (long long)value * (long long)value;
                        value = (squared > max) ? max : (squared < min) ? min : (int)squared;
                    }
                    break; // Square (clamped)
                case 21: 
                    {
                        if (value > 0)
                            value = (int)sqrt((double)value);
                        else
                            value = 0;
                    }
                    break; // Square root
                case 22: value = value << 1; break; // Left shift (multiply by 2)
                case 23: value = value >> 1; break; // Right shift (divide by 2)
                case 24: value = ~value; break; // Bitwise NOT
            }
            
            // Clamp to range (except for overflow/underflow tests and bitwise operations)
            if (mutation_type != 7 && mutation_type != 8 && mutation_type != 24)
            {
                if (value < min) value = min;
                if (value > max) value = max;
            }
            // For bitwise NOT, clamp after operation
            if (mutation_type == 24)
            {
                if (value < min) value = min;
                if (value > max) value = max;
            }
            
            // Write back
            char new_str[32];
            int new_len = snprintf(new_str, 32, "%d", value);
            if (new_len < available_len)
            {
                memcpy(buf + offset, new_str, new_len);
                // Pad with spaces if needed
                for (int i = new_len; i < available_len && i < len; i++)
                {
                    buf[offset + i] = ' ';
                }
            }
            else
            {
                memcpy(buf + offset, new_str, available_len);
            }
            ck_free(str);
            break;
        }
        
        case CONSTRAINT_STRING:
        {
            int min_len = constraint->constraint.string_range.min_len;
            int max_len = constraint->constraint.string_range.max_len;
            
            // Format-aware mutation: detect format first
            int is_email = is_email_format(buf + offset, available_len);
            int is_url = is_url_format(buf + offset, available_len);
            int is_base64 = is_base64_format(buf + offset, available_len);
            
            // Use Multi-Armed Bandit to select mutation operator
            multi_armed_bandit_t *mab = NULL;
            int mutation_type = 0;
            if (mab_enabled && (mab = get_mab_for_constraint(CONSTRAINT_STRING)))
            {
                mutation_type = (int)mab_select_arm(mab);
                last_constraint_type = CONSTRAINT_STRING;
                last_selected_operator = mutation_type;
            }
            else
            {
                // Fallback to random if MAB not enabled or not available
                mutation_type = (int)(random() % 20);
            }
            
            // Format-specific mutations (cases 0-2)
            if (mutation_type == 0 && is_email)
            {
                // Email format mutation
                if (available_len > 10)
                {
                    const char *email_variants[] = {
                        "test@[127.0.0.1]",
                        "test@[IPv6::1]",
                        "a\"@example.com",
                        "test@example.com",
                        "verylongemailaddressthatmightexceedlimits@example.com"
                    };
                    const char *email = email_variants[random() % 5];
                    int email_len = strlen(email);
                    memcpy(buf + offset, email, email_len < available_len ? email_len : available_len);
                }
                break;
            }
            if (mutation_type == 1 && is_url)
            {
                // URL format mutation
                if (available_len > 15)
                {
                    const char *url_variants[] = {
                        "http://example.com/path%00",
                        "http://example.com/path<script>",
                        "http://example.com/%2e%2e/etc/passwd",
                        "file:///etc/passwd",
                        "ftp://anonymous:anonymous@example.com"
                    };
                    const char *url = url_variants[random() % 5];
                    int url_len = strlen(url);
                    memcpy(buf + offset, url, url_len < available_len ? url_len : available_len);
                }
                break;
            }
            if (mutation_type == 2 && is_base64)
            {
                // Base64 format mutation
                if (available_len > 4)
                {
                    const char *base64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";
                    for (int i = 0; i < available_len && (offset + i) < len; i++)
                    {
                        buf[offset + i] = base64_chars[random() % 65];
                    }
                }
                break;
            }
            
            // General string mutations (cases 3-19)
            switch (mutation_type)
            {
                case 3: // Change random character
                    if (available_len > 0)
                    {
                        int pos = random() % available_len;
                        buf[offset + pos] = 32 + (random() % 95);
                    }
                    break;
                case 4: // Set to min length
                    if (min_len > 0 && min_len <= available_len)
                    {
                        memset(buf + offset, 'A', min_len);
                        if (min_len < available_len)
                        {
                            memset(buf + offset + min_len, '\0', available_len - min_len);
                        }
                    }
                    break;
                case 5: // Set to max length (fill with 'A')
                    if (max_len > 0 && max_len <= available_len)
                    {
                        memset(buf + offset, 'A', max_len);
                        if (max_len < available_len)
                        {
                            memset(buf + offset + max_len, '\0', available_len - max_len);
                        }
                    }
                    break;
                case 6: // Overflow test (exceed max length)
                    if (available_len > 0)
                    {
                        int overflow_len = max_len + 100;
                        if (overflow_len > available_len) overflow_len = available_len;
                        memset(buf + offset, 'A', overflow_len);
                    }
                    break;
                case 7: // Empty string
                    memset(buf + offset, '\0', available_len < len ? available_len : len - offset);
                    break;
                case 8: // Repeat character pattern
                    if (available_len > 0)
                    {
                        memset(buf + offset, 'A', available_len < len ? available_len : len - offset);
                    }
                    break;
                case 9: // Pattern repeat (ABC pattern)
                    if (available_len > 0)
                    {
                        const char *pattern = "ABC";
                        int pattern_len = 3;
                        for (int i = 0; i < available_len && (offset + i) < len; i++)
                        {
                            buf[offset + i] = pattern[i % pattern_len];
                        }
                    }
                    break;
                case 10: // Extended special characters
                    if (available_len > 0)
                    {
                        const char *extended_special = "\x00\x01\x02\x03\xff\xfe\xfd\n\r\t\"'\\<>{}[]()";
                        int pos = random() % available_len;
                        int special_len = strlen(extended_special);
                        buf[offset + pos] = extended_special[random() % special_len];
                    }
                    break;
                case 11: // UTF-8 boundary test
                    if (available_len >= 3)
                    {
                        const char *invalid_utf8 = "\xc0\xc1\xf5\xff";
                        int pos = random() % (available_len - 2);
                        buf[offset + pos] = invalid_utf8[random() % 4];
                    }
                    break;
                case 12: // Control characters injection
                    if (available_len > 0)
                    {
                        const char *control_chars = "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f";
                        int pos = random() % available_len;
                        buf[offset + pos] = control_chars[random() % 13];
                    }
                    break;
                case 13: // High byte characters
                    if (available_len > 0)
                    {
                        const char *high_bytes = "\x80\x81\x82\x83\xff\xfe\xfd\xfc";
                        int pos = random() % available_len;
                        buf[offset + pos] = high_bytes[random() % 8];
                    }
                    break;
                case 14: // Format string attack patterns
                    if (available_len > 5)
                    {
                        const char *format_strings[] = {
                            "%s%s%s%s%s",
                            "%n%n%n%n",
                            "%x%x%x%x",
                            "%p%p%p%p"
                        };
                        const char *fmt = format_strings[random() % 4];
                        int fmt_len = strlen(fmt);
                        memcpy(buf + offset, fmt, fmt_len < available_len ? fmt_len : available_len);
                    }
                    break;
                case 15: // SQL injection patterns
                    if (available_len > 10)
                    {
                        const char *sql_patterns[] = {
                            "' OR '1'='1",
                            "'; DROP TABLE--",
                            "' UNION SELECT--",
                            "1' OR '1'='1"
                        };
                        const char *sql = sql_patterns[random() % 4];
                        int sql_len = strlen(sql);
                        memcpy(buf + offset, sql, sql_len < available_len ? sql_len : available_len);
                    }
                    break;
                case 16: // XSS patterns
                    if (available_len > 10)
                    {
                        const char *xss_patterns[] = {
                            "<script>alert(1)</script>",
                            "<img src=x onerror=alert(1)>",
                            "javascript:alert(1)",
                            "<svg onload=alert(1)>"
                        };
                        const char *xss = xss_patterns[random() % 4];
                        int xss_len = strlen(xss);
                        memcpy(buf + offset, xss, xss_len < available_len ? xss_len : available_len);
                    }
                    break;
                case 17: // Path traversal in string
                    if (available_len > 10)
                    {
                        const char *traversal = "../../../etc/passwd";
                        int trav_len = strlen(traversal);
                        memcpy(buf + offset, traversal, trav_len < available_len ? trav_len : available_len);
                    }
                    break;
                case 18: // Null byte injection
                    if (available_len > 5)
                    {
                        memcpy(buf + offset, "test", 4);
                        buf[offset + 4] = '\0';
                        if (available_len > 5)
                            memcpy(buf + offset + 5, "suffix", available_len - 5 < 6 ? available_len - 5 : 6);
                    }
                    break;
                case 19: // Unicode normalization attacks
                    if (available_len > 10)
                    {
                        // Try to inject confusable Unicode characters
                        const char *unicode_test = "\xc2\xa0\xe2\x80\x8b\xe2\x80\x8c"; // Non-breaking space, zero-width chars
                        int unicode_len = strlen(unicode_test);
                        memcpy(buf + offset, unicode_test, unicode_len < available_len ? unicode_len : available_len);
                    }
                    break;
            }
            break;
        }
        
        case CONSTRAINT_ENUM:
        {
            // Enhanced enum mutation: 8 strategies
            int count = constraint->constraint.enum_values.count;
            if (count > 0)
            {
                // Use Multi-Armed Bandit to select mutation operator
                multi_armed_bandit_t *mab = NULL;
                int mutation_type = 0;
                if (mab_enabled && (mab = get_mab_for_constraint(CONSTRAINT_ENUM)))
                {
                    mutation_type = (int)mab_select_arm(mab);
                    last_constraint_type = CONSTRAINT_ENUM;
                    last_selected_operator = mutation_type;
                }
                else
                {
                    // Fallback to random if MAB not enabled or not available
                    mutation_type = (int)(random() % 8);
                }
                const char *new_value = NULL;
                int idx = 0;
                
                switch (mutation_type)
                {
                    case 0: // Random selection
                        idx = random() % count;
                        new_value = constraint->constraint.enum_values.values[idx];
                        break;
                    case 1: // First value
                        idx = 0;
                        new_value = constraint->constraint.enum_values.values[idx];
                        break;
                    case 2: // Last value
                        idx = count - 1;
                        new_value = constraint->constraint.enum_values.values[idx];
                        break;
                    case 3: // Middle value
                        idx = count / 2;
                        new_value = constraint->constraint.enum_values.values[idx];
                        break;
                    case 4: // Similar value mutation (case variation)
                        idx = random() % count;
                        new_value = constraint->constraint.enum_values.values[idx];
                        // Mutate first character case
                        if (available_len > 0 && new_value != NULL && new_value[0] != '\0')
                        {
                            int new_len = strlen(new_value);
                            if (new_len < available_len)
                            {
                                memcpy(buf + offset, new_value, new_len);
                                // Toggle case of first character
                                if (buf[offset] >= 'A' && buf[offset] <= 'Z')
                                    buf[offset] += 32;
                                else if (buf[offset] >= 'a' && buf[offset] <= 'z')
                                    buf[offset] -= 32;
                                // Pad with spaces
                                for (int i = new_len; i < available_len && i < len; i++)
                                {
                                    buf[offset + i] = ' ';
                                }
                            }
                            else
                            {
                                memcpy(buf + offset, new_value, available_len);
                                // Toggle case if possible
                                if (buf[offset] >= 'A' && buf[offset] <= 'Z')
                                    buf[offset] += 32;
                                else if (buf[offset] >= 'a' && buf[offset] <= 'z')
                                    buf[offset] -= 32;
                            }
                        }
                        else if (new_value != NULL)
                        {
                            // Fallback: just copy the value
                            int new_len = strlen(new_value);
                            memcpy(buf + offset, new_value, new_len < available_len ? new_len : available_len);
                        }
                        break;
                    case 5: // Similar value with typo (add character)
                        idx = random() % count;
                        new_value = constraint->constraint.enum_values.values[idx];
                        if (new_value != NULL)
                        {
                            int new_len = strlen(new_value);
                            // Add a character at the end if space allows
                            if (available_len > new_len)
                            {
                                memcpy(buf + offset, new_value, new_len);
                                buf[offset + new_len] = 'X'; // Add typo
                                for (int i = new_len + 1; i < available_len && i < len; i++)
                                {
                                    buf[offset + i] = ' ';
                                }
                            }
                            else
                            {
                                // No space for typo, just copy and maybe modify last char
                                memcpy(buf + offset, new_value, available_len);
                                if (available_len > 0)
                                {
                                    buf[offset + available_len - 1] = 'X'; // Replace last char
                                }
                            }
                        }
                        break;
                    case 6: // Similar value with typo (remove character)
                        idx = random() % count;
                        new_value = constraint->constraint.enum_values.values[idx];
                        if (new_value != NULL && strlen(new_value) > 1)
                        {
                            int new_len = strlen(new_value) - 1;
                            if (new_len < available_len)
                            {
                                memcpy(buf + offset, new_value, new_len);
                                // Pad with spaces
                                for (int i = new_len; i < available_len && i < len; i++)
                                {
                                    buf[offset + i] = ' ';
                                }
                            }
                            else
                            {
                                memcpy(buf + offset, new_value, available_len);
                            }
                        }
                        else if (new_value != NULL)
                        {
                            int new_len = strlen(new_value);
                            memcpy(buf + offset, new_value, new_len < available_len ? new_len : available_len);
                        }
                        break;
                    case 7: // Combine two enum values (if space allows)
                        if (count >= 2 && available_len > 10)
                        {
                            idx = random() % count;
                            int idx2 = random() % count;
                            while (idx2 == idx) idx2 = random() % count;
                            const char *val1 = constraint->constraint.enum_values.values[idx];
                            const char *val2 = constraint->constraint.enum_values.values[idx2];
                            int len1 = strlen(val1);
                            int len2 = strlen(val2);
                            if (len1 + len2 + 1 < available_len)
                            {
                                memcpy(buf + offset, val1, len1);
                                buf[offset + len1] = '_';
                                memcpy(buf + offset + len1 + 1, val2, len2 < available_len - len1 - 1 ? len2 : available_len - len1 - 1);
                            }
                            else
                            {
                                // Fallback to single value
                                new_value = val1;
                            }
                        }
                        else
                        {
                            idx = random() % count;
                            new_value = constraint->constraint.enum_values.values[idx];
                        }
                        break;
                }
                
                if (mutation_type < 4 && new_value != NULL)
                {
                    int new_len = strlen(new_value);
                    if (new_len < available_len)
                    {
                        memcpy(buf + offset, new_value, new_len);
                        // Pad with spaces
                        for (int i = new_len; i < available_len && i < len; i++)
                        {
                            buf[offset + i] = ' ';
                        }
                    }
                    else
                    {
                        memcpy(buf + offset, new_value, available_len);
                    }
                }
            }
            break;
        }
        
        case CONSTRAINT_IP:
        {
            // Enhanced IP mutation: 15 strategies with MAB
            multi_armed_bandit_t *mab = NULL;
            int mutation_type = 0;
            if (mab_enabled && (mab = get_mab_for_constraint(CONSTRAINT_IP)))
            {
                mutation_type = (int)mab_select_arm(mab);
                last_constraint_type = CONSTRAINT_IP;
                last_selected_operator = mutation_type;
            }
            else
            {
                mutation_type = (int)(random() % 15);
            }
            const char *special_ips[] = {
                "0.0.0.0",           // All zeros
                "255.255.255.255",   // Broadcast
                "127.0.0.1",         // Loopback
                "192.168.0.1",       // Private network
                "10.0.0.1",          // Private network
                "172.16.0.1",        // Private network
                "224.0.0.1",         // Multicast
                "169.254.0.1",       // Link local
            };
            const char *invalid_formats[] = {
                "999.999.999.999",   // Out of range
                "256.1.1.1",         // Exceeds 255
                "1.1.1",             // Missing segment
                "1.1.1.1.1",         // Extra segment
            };
            
            switch (mutation_type)
            {
                case 0: // Random IP
                {
                    char ip[16];
                    snprintf(ip, 16, "%d.%d.%d.%d", 
                             (int)(random() % 256), (int)(random() % 256), 
                             (int)(random() % 256), (int)(random() % 256));
                    int ip_len = strlen(ip);
                    memcpy(buf + offset, ip, ip_len < available_len ? ip_len : available_len);
                    break;
                }
                case 1: // Invalid IP format
                {
                    const char *invalid = invalid_formats[random() % 4];
                    int invalid_len = strlen(invalid);
                    memcpy(buf + offset, invalid, invalid_len < available_len ? invalid_len : available_len);
                    break;
                }
                case 2: // Special IP addresses
                {
                    const char *special = special_ips[random() % 8];
                    int special_len = strlen(special);
                    memcpy(buf + offset, special, special_len < available_len ? special_len : available_len);
                    break;
                }
                case 3: // IPv6 loopback
                {
                    const char *ipv6 = "::1";
                    int ipv6_len = strlen(ipv6);
                    memcpy(buf + offset, ipv6, ipv6_len < available_len ? ipv6_len : available_len);
                    break;
                }
                case 4: // IPv6 address
                {
                    const char *ipv6 = "2001:db8::1";
                    int ipv6_len = strlen(ipv6);
                    memcpy(buf + offset, ipv6, ipv6_len < available_len ? ipv6_len : available_len);
                    break;
                }
                case 5: // IPv4-mapped IPv6
                {
                    const char *ipv6 = "::ffff:192.0.2.1";
                    int ipv6_len = strlen(ipv6);
                    memcpy(buf + offset, ipv6, ipv6_len < available_len ? ipv6_len : available_len);
                    break;
                }
                case 6: // CIDR notation
                {
                    char cidr[32];
                    snprintf(cidr, 32, "%d.%d.%d.%d/%d", 
                             (int)(random() % 256), (int)(random() % 256), 
                             (int)(random() % 256), (int)(random() % 256),
                             (int)(random() % 33));
                    int cidr_len = strlen(cidr);
                    memcpy(buf + offset, cidr, cidr_len < available_len ? cidr_len : available_len);
                    break;
                }
                case 7: // IP with port
                {
                    char ip_port[32];
                    snprintf(ip_port, 32, "%d.%d.%d.%d:%d", 
                             (int)(random() % 256), (int)(random() % 256), 
                             (int)(random() % 256), (int)(random() % 256),
                             (int)(random() % 65536));
                    int ip_port_len = strlen(ip_port);
                    memcpy(buf + offset, ip_port, ip_port_len < available_len ? ip_port_len : available_len);
                    break;
                }
                case 8: // Boundary IP (min)
                {
                    const char *boundary = "0.0.0.0";
                    int boundary_len = strlen(boundary);
                    memcpy(buf + offset, boundary, boundary_len < available_len ? boundary_len : available_len);
                    break;
                }
                case 9: // Boundary IP (max)
                {
                    const char *boundary = "255.255.255.255";
                    int boundary_len = strlen(boundary);
                    memcpy(buf + offset, boundary, boundary_len < available_len ? boundary_len : available_len);
                    break;
                }
                case 10: // IP with invalid port separator
                {
                    char ip_invalid[32];
                    snprintf(ip_invalid, 32, "%d.%d.%d.%d#%d", 
                             (int)(random() % 256), (int)(random() % 256), 
                             (int)(random() % 256), (int)(random() % 256),
                             (int)(random() % 65536));
                    int ip_invalid_len = strlen(ip_invalid);
                    memcpy(buf + offset, ip_invalid, ip_invalid_len < available_len ? ip_invalid_len : available_len);
                    break;
                }
                case 11: // IPv6 compressed format
                {
                    const char *ipv6_compressed = "2001::1";
                    int ipv6_len = strlen(ipv6_compressed);
                    memcpy(buf + offset, ipv6_compressed, ipv6_len < available_len ? ipv6_len : available_len);
                    break;
                }
                case 12: // IPv6 full format
                {
                    const char *ipv6_full = "2001:0db8:85a3:0000:0000:8a2e:0370:7334";
                    int ipv6_len = strlen(ipv6_full);
                    memcpy(buf + offset, ipv6_full, ipv6_len < available_len ? ipv6_len : available_len);
                    break;
                }
                case 13: // Invalid IPv4 segments
                {
                    const char *invalid_segments[] = {
                        "256.256.256.256",
                        "-1.-1.-1.-1",
                        "999.999.999.999"
                    };
                    const char *invalid = invalid_segments[random() % 3];
                    int invalid_len = strlen(invalid);
                    memcpy(buf + offset, invalid, invalid_len < available_len ? invalid_len : available_len);
                    break;
                }
                case 14: // IP with spaces (invalid)
                {
                    char ip_spaces[32];
                    snprintf(ip_spaces, 32, "%d . %d . %d . %d", 
                             (int)(random() % 256), (int)(random() % 256), 
                             (int)(random() % 256), (int)(random() % 256));
                    int ip_spaces_len = strlen(ip_spaces);
                    memcpy(buf + offset, ip_spaces, ip_spaces_len < available_len ? ip_spaces_len : available_len);
                    break;
                }
            }
            break;
        }
        
        case CONSTRAINT_PATH:
        {
            // Enhanced path mutation: 15 strategies with MAB
            multi_armed_bandit_t *mab = NULL;
            int mutation_type = 0;
            if (mab_enabled && (mab = get_mab_for_constraint(CONSTRAINT_PATH)))
            {
                mutation_type = (int)mab_select_arm(mab);
                last_constraint_type = CONSTRAINT_PATH;
                last_selected_operator = mutation_type;
            }
            else
            {
                mutation_type = (int)(random() % 15);
            }
            const char *traversal_patterns[] = {
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32",
                "....//....//etc/passwd",
                "..%2f..%2fetc%2fpasswd",
                "%2e%2e%2f%2e%2e%2f",
                "..%252f..%252f",
            };
            const char *special_paths[] = {
                "/",
                "//",
                "/././",
                "/tmp/",
                "C:\\",
                "\\\\?\\C:\\",
                "/proc/self/",
                "/dev/null",
                "NUL",
            };
            
            switch (mutation_type)
            {
                case 0: // Path traversal variants
                {
                    const char *traversal = traversal_patterns[random() % 6];
                    int trav_len = strlen(traversal);
                    memcpy(buf + offset, traversal, trav_len < available_len ? trav_len : available_len);
                    break;
                }
                case 1: // Special paths
                {
                    const char *special = special_paths[random() % 9];
                    int special_len = strlen(special);
                    memcpy(buf + offset, special, special_len < available_len ? special_len : available_len);
                    break;
                }
                case 2: // Long path
                {
                    const char *long_path = "/very/long/path/that/exceeds/normal/length";
                    int path_len = strlen(long_path);
                    memcpy(buf + offset, long_path, path_len < available_len ? path_len : available_len);
                    break;
                }
                case 3: // Deep nested path
                {
                    if (available_len > 0)
                    {
                        int depth = 50;
                        int pos = 0;
                        for (int i = 0; i < depth && pos < available_len && (offset + pos) < len; i++)
                        {
                            if (pos + 3 < available_len)
                            {
                                memcpy(buf + offset + pos, "../", 3);
                                pos += 3;
                            }
                            else break;
                        }
                        if (pos < available_len)
                        {
                            memcpy(buf + offset + pos, "etc/passwd", available_len - pos < 10 ? available_len - pos : 10);
                        }
                    }
                    break;
                }
                case 4: // Command injection attempt
                {
                    const char *injections[] = {
                        "/tmp/file; rm -rf /",
                        "/tmp/file|cat /etc/passwd",
                        "/tmp/file$(whoami)",
                    };
                    const char *injection = injections[random() % 3];
                    int inj_len = strlen(injection);
                    memcpy(buf + offset, injection, inj_len < available_len ? inj_len : available_len);
                    break;
                }
                case 5: // Windows long path
                {
                    const char *win_long = "\\\\?\\C:\\very\\long\\path";
                    int win_len = strlen(win_long);
                    memcpy(buf + offset, win_long, win_len < available_len ? win_len : available_len);
                    break;
                }
                case 6: // URL encoded traversal
                {
                    const char *encoded = "..%2f..%2f..%2fetc%2fpasswd";
                    int enc_len = strlen(encoded);
                    memcpy(buf + offset, encoded, enc_len < available_len ? enc_len : available_len);
                    break;
                }
                case 7: // Double encoded
                {
                    const char *double_enc = "..%252f..%252f";
                    int dbl_len = strlen(double_enc);
                    memcpy(buf + offset, double_enc, dbl_len < available_len ? dbl_len : available_len);
                    break;
                }
                case 8: // Special characters
                {
                    if (available_len > 0)
                    {
                        buf[offset] = '/';
                        for (int i = 1; i < available_len && (offset + i) < len; i++)
                        {
                            buf[offset + i] = 32 + (random() % 95);
                        }
                    }
                    break;
                }
                case 9: // Null byte injection
                {
                    if (available_len > 5)
                    {
                        memcpy(buf + offset, "/etc", 4);
                        buf[offset + 4] = '\0';
                        memcpy(buf + offset + 5, "/passwd", available_len - 5 < 7 ? available_len - 5 : 7);
                    }
                    break;
                }
                case 10: // UTF-8 encoded traversal
                {
                    const char *utf8_traversal = "..%c0%af..%c0%af";
                    int utf8_len = strlen(utf8_traversal);
                    memcpy(buf + offset, utf8_traversal, utf8_len < available_len ? utf8_len : available_len);
                    break;
                }
                case 11: // Windows UNC path
                {
                    const char *unc_path = "\\\\server\\share\\file";
                    int unc_len = strlen(unc_path);
                    memcpy(buf + offset, unc_path, unc_len < available_len ? unc_len : available_len);
                    break;
                }
                case 12: // Very long path (exceed limits)
                {
                    if (available_len > 0)
                    {
                        int pos = 0;
                        for (int i = 0; i < 200 && pos < available_len && (offset + pos) < len; i++)
                        {
                            if (pos + 4 < available_len)
                            {
                                memcpy(buf + offset + pos, "dir/", 4);
                                pos += 4;
                            }
                            else break;
                        }
                    }
                    break;
                }
                case 13: // Mixed separators
                {
                    const char *mixed = "/path\\to\\file";
                    int mixed_len = strlen(mixed);
                    memcpy(buf + offset, mixed, mixed_len < available_len ? mixed_len : available_len);
                    break;
                }
                case 14: // Path with special Unicode
                {
                    // Non-breaking space (UTF-8: 0xC2 0xA0)
                    const unsigned char unicode_bytes[] = { '/', 'p', 'a', 't', 'h', '/', 0xC2, 0xA0, 'f', 'i', 'l', 'e', '\0' };
                    const char *unicode_path = (const char *)unicode_bytes;
                    int unicode_len = strlen(unicode_path);
                    memcpy(buf + offset, unicode_path, unicode_len < available_len ? unicode_len : available_len);
                    break;
                }
            }
            break;
        }
        
        case CONSTRAINT_HEX:
        {
            // Enhanced hex mutation: 12 strategies with MAB
            multi_armed_bandit_t *mab = NULL;
            int mutation_type = 0;
            if (mab_enabled && (mab = get_mab_for_constraint(CONSTRAINT_HEX)))
            {
                mutation_type = (int)mab_select_arm(mab);
                last_constraint_type = CONSTRAINT_HEX;
                last_selected_operator = mutation_type;
            }
            else
            {
                mutation_type = (int)(random() % 12);
            }
            const char *hex_chars = "0123456789ABCDEFabcdef";
            const char *special_hex[] = {
                "00000000",        // All zeros
                "FFFFFFFF",        // All F
                "DEADBEEF",        // Common test value
                "CAFEBABE",        // Java magic number
            };
            
            switch (mutation_type)
            {
                case 0: // Change random character
                    if (available_len > 0)
                    {
                        int pos = random() % available_len;
                        buf[offset + pos] = hex_chars[random() % 22];
                    }
                    break;
                case 1: // Special hex values
                {
                    const char *special = special_hex[random() % 4];
                    int special_len = strlen(special);
                    memcpy(buf + offset, special, special_len < available_len ? special_len : available_len);
                    break;
                }
                case 2: // Odd length (invalid hex)
                    if (available_len > 0)
                    {
                        // Make it odd length by setting last char to non-hex
                        int pos = available_len - 1;
                        if (pos >= 0 && (offset + pos) < len)
                        {
                            buf[offset + pos] = 'X';
                        }
                    }
                    break;
                case 3: // Mixed case
                    if (available_len > 0)
                    {
                        for (int i = 0; i < available_len && (offset + i) < len; i++)
                        {
                            if (random() % 2)
                                buf[offset + i] = hex_chars[random() % 16]; // 0-9A-F
                            else
                                buf[offset + i] = hex_chars[10 + random() % 6]; // a-f
                        }
                    }
                    break;
                case 4: // With 0x prefix
                    if (available_len >= 2)
                    {
                        memcpy(buf + offset, "0x", 2);
                        for (int i = 2; i < available_len && (offset + i) < len; i++)
                        {
                            buf[offset + i] = hex_chars[random() % 16];
                        }
                    }
                    break;
                case 5: // With separators (colons)
                    if (available_len >= 11)
                    {
                        const char *with_colons = "FF:FF:FF:FF";
                        int colons_len = strlen(with_colons);
                        memcpy(buf + offset, with_colons, colons_len < available_len ? colons_len : available_len);
                    }
                    else if (available_len > 0)
                    {
                        // Fill with hex chars
                        for (int i = 0; i < available_len && (offset + i) < len; i++)
                        {
                            buf[offset + i] = hex_chars[random() % 16];
                        }
                    }
                    break;
                case 6: // With separators (dashes)
                    if (available_len >= 11)
                    {
                        const char *with_dashes = "FF-FF-FF-FF";
                        int dashes_len = strlen(with_dashes);
                        memcpy(buf + offset, with_dashes, dashes_len < available_len ? dashes_len : available_len);
                    }
                    else if (available_len > 0)
                    {
                        for (int i = 0; i < available_len && (offset + i) < len; i++)
                        {
                            buf[offset + i] = hex_chars[random() % 16];
                        }
                    }
                    break;
                case 7: // Empty/null
                    memset(buf + offset, '\0', available_len < len ? available_len : len - offset);
                    break;
                case 8: // Special hex patterns
                {
                    const char *special_patterns[] = {
                        "0xDEADBEEF",
                        "0xCAFEBABE",
                        "0xBAADF00D",
                        "0xDEADC0DE"
                    };
                    const char *pattern = special_patterns[random() % 4];
                    int pattern_len = strlen(pattern);
                    memcpy(buf + offset, pattern, pattern_len < available_len ? pattern_len : available_len);
                    break;
                }
                case 9: // Hex with spaces
                {
                    if (available_len >= 11)
                    {
                        const char *hex_spaces = "FF FF FF FF";
                        int hex_spaces_len = strlen(hex_spaces);
                        memcpy(buf + offset, hex_spaces, hex_spaces_len < available_len ? hex_spaces_len : available_len);
                    }
                    break;
                }
                case 10: // Invalid hex characters
                {
                    if (available_len > 0)
                    {
                        const char *invalid_hex = "GHIJKLMNOPQRSTUVWXYZ";
                        for (int i = 0; i < available_len && (offset + i) < len; i++)
                        {
                            buf[offset + i] = invalid_hex[i % strlen(invalid_hex)];
                        }
                    }
                    break;
                }
                case 11: // Hex with 0X prefix (uppercase)
                {
                    if (available_len >= 2)
                    {
                        memcpy(buf + offset, "0X", 2);
                        for (int i = 2; i < available_len && (offset + i) < len; i++)
                        {
                            buf[offset + i] = hex_chars[random() % 16];
                        }
                    }
                    break;
                }
            }
            break;
        }
        
        default:
            // Generic mutation: flip random bit
            if (available_len > 0)
            {
                int pos = random() % available_len;
                buf[offset + pos] ^= (1 << (random() % 8));
            }
            break;
    }
}