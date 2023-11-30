"""Script that generates plots for all figures."""


import contextlib

from paper1_code.scripts import gen_fig1, gen_fig2, gen_fig3, gen_fig4, gen_fig5


def main(show_output: bool = False):
    """Run the main program."""
    gen_fig1.main(show_output)
    gen_fig2.main(show_output)
    gen_fig3.main(show_output)
    gen_fig4.main(show_output)
    with contextlib.suppress(NotImplementedError):
        gen_fig5.main()


if __name__ == "__main__":
    main(show_output=True)
