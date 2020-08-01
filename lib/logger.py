import click
import logging


class Logger:
    VERBOSITY_DEBUG = 3
    VERBOSITY_INFO = 2
    VERBOSITY_WARNING = 1
    VERBOSITY_NORMAL = 0

    LOG_LEVEL_ERROR = 40
    LOG_LEVEL_WARNING = 30
    LOG_LEVEL_INFO = 20
    LOG_LEVEL_DEBUG = 10
    LOG_LEVEL_SILENT = 0

    inited = False
    logger = None

    def __init__(self, log_file=None, name='processing-logger', print_verbosity=VERBOSITY_NORMAL,
                 log_verbosity=VERBOSITY_INFO, delay_init=False):
        if not delay_init:
            self.init_logger(log_file=log_file, name=name, log_verbosity=log_verbosity)
        self.print_verbosity = print_verbosity
        self.log_verbosity = log_verbosity

    def init_logger(self, log_file, name, log_verbosity):
        if self.inited:
            raise Exception('Logger already initialized.')

        logger = logging.getLogger(name)
        logger.setLevel(log_verbosity)

        # Set formatter.
        formatter = logging.Formatter(fmt='{asctime}: {levelname}: {message}', style='{')

        # Auto pick file handler or stream handler.
        if log_file:
            handler = logging.FileHandler(log_file)
        else:
            handler = logging.StreamHandler()

        handler.setLevel(log_verbosity)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        self.logger = logger
        self.inited = True

    def log(self, msg, level=LOG_LEVEL_DEBUG, exc_info=None, print_only=False, log_only=False):
        if level == self.LOG_LEVEL_DEBUG:
            verbosity_required = self.VERBOSITY_DEBUG
        elif level == self.LOG_LEVEL_INFO:
            verbosity_required = self.VERBOSITY_INFO
        elif level == self.LOG_LEVEL_WARNING:
            verbosity_required = self.VERBOSITY_WARNING
        elif level == self.LOG_LEVEL_ERROR:
            verbosity_required = self.VERBOSITY_NORMAL
            if not exc_info:
                exc_info = True
        else:
            raise Exception('Unknown log level.')

        if self.print_verbosity >= verbosity_required and not log_only:
            click.echo(msg)

        if self.log_verbosity >= verbosity_required and not print_only:
            self.logger.log(level=level, msg=msg, exc_info=exc_info)

        return

    def log_block(self, title, msg, level=LOG_LEVEL_DEBUG, exc_info=None, print_only=False):
        self.log(msg='\n\n========================================\n' + title
                     + '\n----------------------------------------\n' + msg
                     + '\n========================================\n',
                 level=level, exc_info=exc_info, print_only=print_only)

        return

    def print(self, msg, level=LOG_LEVEL_WARNING):
        return self.log(msg=msg, level=level, print_only=True)

    def exception_handler(self, exctype, value, traceback):
        self.log(msg=f'Error type: {exctype}\nError value: {value}',
                 level=self.LOG_LEVEL_ERROR,
                 exc_info=(exctype, value, traceback))
