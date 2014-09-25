import run_tests


def import_tests():
    from trove.tests.examples import snippets


if __name__=="__main__":
    run_tests.run_super_fake_mode(import_tests)
