/* A tiny native executable also verifies the final image's dynamic dependencies. */
#include <stdio.h>
#include <string.h>
#include <td/telegram/td_json_client.h>

int main(void) {
    const char *requests[] = {
        "{\"@type\":\"getOption\",\"name\":\"version\"}",
        "{\"@type\":\"getOption\",\"name\":\"commit_hash\"}",
        "{\"@type\":\"parseTextEntities\",\"text\":\"<b>TDLib</b>\",\"parse_mode\":{\"@type\":\"textParseModeHTML\"}}"
    };
    const char *types[] = {"optionValueString", "optionValueString", "formattedText"};
    for (unsigned int i = 0; i < sizeof(requests) / sizeof(requests[0]); ++i) {
        const char *result = td_execute(requests[i]);
        if (result == NULL || strstr(result, types[i]) == NULL) {
            fprintf(stderr, "TDLib JSON check failed: %s\n", result ? result : "null");
            return 1;
        }
        puts(result);
    }
    puts("TDLib is a library, not a running Telegram or HTTP server.");
    puts("Usage and examples: https://github.com/vigarepo2/TDLib");
    return 0;
}
