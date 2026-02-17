#ifndef __CHAT_LLM_H
#define __CHAT_LLM_H

#include "klist.h"
#include "kvec.h"
#include "khash.h"
#include "types.h"
#include <json-c/json.h>
#include <stdint.h>

/*
There are 2048 tokens available, around 270 are used for the initial data for the stall prompt
We give at most 400 for the examples and 1300 for the stall prompt
Similarly 1700 is for the example request in the seed enrichment
*/

/*
 * LLM configuration (anonymous-release friendly)
 *
 * This project uses an OpenAI-compatible HTTP API. DO NOT hardcode secrets.
 *
 * Required:
 *   - XPGFUZZ_LLM_API_KEY
 *
 * Optional:
 *   - XPGFUZZ_LLM_BASE_URL   (default: https://www.dmxapi.com/v1)
 *   - XPGFUZZ_LLM_MODEL      (default: DeepSeek-V3.1)
 */
#define XPGFUZZ_LLM_API_KEY_ENV  "XPGFUZZ_LLM_API_KEY"
#define XPGFUZZ_LLM_BASE_URL_ENV "XPGFUZZ_LLM_BASE_URL"
#define XPGFUZZ_LLM_MODEL_ENV    "XPGFUZZ_LLM_MODEL"

#define XPGFUZZ_LLM_DEFAULT_BASE_URL "https://www.dmxapi.com/v1"
#define XPGFUZZ_LLM_DEFAULT_MODEL    "DeepSeek-V3.1"

#define MAX_PROMPT_LENGTH 2048
#define EXAMPLES_PROMPT_LENGTH 400
#define HISTORY_PROMPT_LENGTH 1300
#define EXAMPLE_SEQUENCE_PROMPT_LENGTH 1700

#define TEMPLATE_CONSISTENCY_COUNT 7

// Maximum amount of retries for the state stall
#define STALL_RETRIES 1

// Maximum amount of tries to get the grammars
#define GRAMMAR_RETRIES 5

// Maximum amount
#define MESSAGE_TYPE_RETRIES 5

//Maximum amount of tries for an enrichment
#define ENRICHMENT_RETRIES 5

// Maximum number of messages to be added
#define MAX_ENRICHMENT_MESSAGE_TYPES 2

// Maximum number of messages to examine for addition
#define MAX_ENRICHMENT_CORPUS_SIZE 10

#define PCRE2_CODE_UNIT_WIDTH 8 // Characters are 8 bits
#include <pcre2.h>

// Init KLIST with JSON object
#define __grammar_t_free(x)
#define __rang_t_free(x)
#define __khash_t_free(x) 
KHASH_SET_INIT_STR(strSet);
KLIST_INIT(gram, json_object *, __grammar_t_free)
KLIST_INIT(rang, pcre2_code **, __rang_t_free)

// Type constraint definitions (must be defined before pattern_with_constraints_t)
typedef enum {
    CONSTRAINT_NONE,    // <<VALUE>>
    CONSTRAINT_INTEGER, // <<INTEGER:min-max>>
    CONSTRAINT_STRING,  // <<STRING:min_len-max_len>>
    CONSTRAINT_ENUM,    // <<ENUM:val1,val2,...>>
    CONSTRAINT_IP,       // <<IP>>
    CONSTRAINT_PATH,    // <<PATH>>
    CONSTRAINT_HEX      // <<HEX>>
} constraint_type_t;

typedef struct {
    constraint_type_t type;
    union {
        struct { int min; int max; } integer_range;
        struct { int min_len; int max_len; } string_range;
        struct { char **values; int count; } enum_values;
    } constraint;
} type_constraint_t;

// Structure to store pattern with constraints
typedef struct {
    pcre2_code **patterns;  // [0] = header pattern, [1] = fields pattern
    type_constraint_t **header_constraints;  // Constraints for header pattern groups
    type_constraint_t **field_constraints;    // Constraints for field pattern groups
    int header_constraint_count;
    int field_constraint_count;
} pattern_with_constraints_t;

typedef struct
{
    int start;
    int len;
    int mutable;
    type_constraint_t *constraint; // Type constraint for this range
} range;

typedef kvec_t(range) range_list;
typedef kvec_t(khash_t(strSet)*) message_set_list;

// define one map to save pairs: {key: string, value: int}
KHASH_MAP_INIT_STR(strMap, int)
KHASH_MAP_INIT_STR(field_table, int);
KHASH_INIT(consistency_table, const char *, khash_t(field_table) *, 1, kh_str_hash_func, kh_str_hash_equal);

// Hash functions for pointer type (defined as macros, similar to kh_int_hash_func)
#define kh_ptr_hash_func(key) (khint_t)((uintptr_t)(key))
#define kh_ptr_hash_equal(a, b) ((a) == (b))

// Map to store constraints for each pattern group
// Key: pattern pointer (as void*), Value: pattern_with_constraints_t*
KHASH_INIT(pattern_constraints_map, void *, pattern_with_constraints_t *, 1, kh_ptr_hash_func, kh_ptr_hash_equal);

char *chat_with_llm(char *prompt, char *model, int tries, float temperature);

/* Environment-backed getters (implemented in chat-llm.c). */
const char *xpgfuzz_llm_get_api_key(void);
const char *xpgfuzz_llm_get_base_url(void);
const char *xpgfuzz_llm_get_model(void);
char *construct_prompt_for_templates(char *protocol_name, char **final_msg);
char *construct_prompt_for_remaining_templates(char *protocol_name, char *templates_prompt, char *templates_answer);
char *construct_prompt_for_protocol_message_types(char *protocol_name);
char *construct_prompt_for_requests_to_states(const char *protocol_name, const char *protocol_state, const char *example_requests);
char *construct_prompt_stall(char *protocol_name, char *examples, char *history);

void extract_message_grammars(char *answers, klist_t(gram) * grammar_set);
char *extract_message_pattern(const char *header_str,
                               khash_t(field_table) * field_table,
                               pcre2_code **patterns,
                               int debug_file,
                               const char *debug_file_name);
pattern_with_constraints_t *get_pattern_constraints(pcre2_code **patterns);
void print_all_constraints_storage(void);  // Print all constraints in storage hash table
char *extract_stalled_message(char *message, size_t message_len);
char *format_request_message(char *message);


range_list starts_with(char *line, int length, pcre2_code *pattern, pcre2_code **patterns_array);
range_list get_mutable_ranges(char *line, int length, int offset, pcre2_code *pattern, pcre2_code **patterns_array);
void get_protocol_message_types(char *state_prompt, khash_t(strSet) * message_types);

char *enrich_sequence(char* sequence, khash_t(strSet) *missing_message_types);
khash_t(strSet)* duplicate_hash(khash_t(strSet)* set);
void write_new_seeds(char *enriched_file, char *contents);
char *unescape_string(const char *input);
char *format_string(char *state_string);
message_set_list message_combinations(khash_t(strSet)* sequence, int size);
// 在现有函数声明后添加  
struct queue_entry *llm_guided_mutation(struct queue_entry *seed);  
char *construct_prompt_for_seed_mutation(char *protocol_name, char *seed_content);

// Multi-Armed Bandit (MAB) for mutation operator selection
// UCB1 algorithm implementation
typedef struct {
    u32 pulls;          // Number of times this operator has been selected
    u32 rewards;        // Total rewards (e.g., new coverage found)
    double avg_reward;  // Average reward
    double ucb_value;   // UCB1 upper confidence bound value
} mab_arm_t;

typedef struct {
    mab_arm_t *arms;    // Array of arms (one per mutation operator)
    u32 num_arms;       // Number of mutation operators
    u32 total_pulls;    // Total number of pulls across all arms
} multi_armed_bandit_t;

// Type constraint functions
type_constraint_t *parse_constraint(const char *str);
void free_constraint(type_constraint_t *constraint);
char *generate_value_by_constraint(type_constraint_t *constraint);
void mutate_value_by_constraint(u8 *buf, u32 len, type_constraint_t *constraint, u32 offset);

// Multi-Armed Bandit functions for mutation operator selection
multi_armed_bandit_t *mab_init(u32 num_arms);
void mab_free(multi_armed_bandit_t *mab);
u32 mab_select_arm(multi_armed_bandit_t *mab);
void mab_update_reward(multi_armed_bandit_t *mab, u32 arm_index, u32 reward);
void mab_update_last_mutation_reward(u32 reward); // Update reward for last mutation operator
void set_mab_enabled(u8 enabled); // Enable or disable MAB for mutation operator selection
#endif // __CHAT_LLM_H