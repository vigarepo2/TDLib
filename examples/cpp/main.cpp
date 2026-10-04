#include <iostream>
#include <td/telegram/td_json_client.h>

int main() {
    const char *result = td_execute(R"({"@type":"getOption","name":"version"})");
    if (result == nullptr) {
        std::cerr << "TDLib did not return a synchronous response\n";
        return 1;
    }
    std::cout << result << '\n';
    return 0;
}
