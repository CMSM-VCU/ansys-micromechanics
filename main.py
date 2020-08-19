import input_handling as ih


def main():
    input_file_paths = ih.get_input_file_paths()

    cases = []

    for input_file in input_file_paths:
        cases.append(ih.parse_input_data(input_file))

    for case in cases:
        case.run_tests()

        print(case.properties)


if __name__ == "__main__":
    main()
