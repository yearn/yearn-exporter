import logging
from functools import lru_cache
from operator import attrgetter
from requests import HTTPError
from typing import Any, Callable, Iterable, List, Optional, Tuple, Union

import sentry_sdk
from dank_mids.helpers import lru_cache_lite
from pony.orm import TransactionError, TransactionIntegrityError
from y import ContractNotVerified

from yearn.entities import TreasuryTx, TxGroup
from yearn.outputs.postgres.utils import cache_txgroup

logger = logging.getLogger(__name__)


class _TxGroup:
    def __init__(self, label: str) -> None:
        self.label = label
        self.children: List[ChildTxGroup] = []
    
    def sort(self, tx: TreasuryTx) -> Optional[TxGroup]:
        for child in self.children:
            if txgroup := child.sort(tx):
                return txgroup
    
    def create_child(self, label: str, check: Optional[Callable] = None) -> "ChildTxGroup":
        return ChildTxGroup(label, self, check=check)


class TopLevelTxGroup(_TxGroup):
    def __init__(self, label: str) -> None:
        super().__init__(label)

    @property
    def txgroup(self):
        return cache_txgroup(self.label)
    
    @property
    def top(self):
        return self.txgroup


class ChildTxGroup(_TxGroup):
    def __init__(self, label: str, parent: TopLevelTxGroup, check: Optional[Callable] = None) -> None:
        super().__init__(label)
        self.parent = parent
        self.parent.children.append(self)
        if check:
            self.check = check
        
    @property
    def txgroup(self):
        return cache_txgroup(self.label, self.parent.txgroup)
        
    @property
    def top(self):
        return self.parent.top
    
    def sort(self, tx: TreasuryTx) -> Optional[TxGroup]:
        if not hasattr(self, 'check'):
            return super().sort(tx)
        try:
            result = self.check(tx)
            if result is True:
                print(f"sorted {tx} to {self.label}")
                return self.txgroup
            elif result is not False:
                raise TypeError(result, self, self.check)
        except ContractNotVerified:
            logger.info("ContractNotVerified when sorting %s with %s", tx, self.label)
        except KeyError as e:
            if str(e) != "'components'":
                # this is some weird brownie thing we dont care about
                raise
        except (AssertionError, AttributeError, TransactionError, HTTPError, NotImplementedError, ValueError, TypeError, NameError) as e:
            logger.exception(e)
            raise
        except Exception as e:
            logger.warning("%s when sorting %s with %s.", e.__repr__(), tx, self.label)
            sentry_sdk.capture_exception(e)
            return None
        return super().sort(tx)


class HashMatcher:
    """
    Used to match a TreasuryTx against a list of hash strings without needing to worry about checksums. Can apply filter functions if necessary for code cleanliness.
    """
    filter: Optional["Filter"] = None

    def __init__(
        self, 
        hashes: Iterable[Union[str, Tuple[str, "Filter"]]], 
        filter: Optional["Filter"] = None,
    ) -> None:
        if filter is None:
            self.hashes = tuple(hash.lower() if isinstance(hash, str) else hash for hash in hashes)
        else:
            self.filter = filter
            assert all(isinstance(hash, str) for hash in hashes)
            self.hashes = tuple(map(str.lower, hashes))
    
    def __contains__(self, tx: TreasuryTx) -> bool:
        if self.filter is not None:
            return tx in self.filter and tx.hash in self.hashes
        for matcher in self.hashes:
            if isinstance(matcher, str):
                if tx.hash == matcher:
                    return True
            else:
                matcher, filter = matcher
                if tx.hash == matcher and tx in filter:
                    return True
        return False
    
    def contains(self, tx: TreasuryTx) -> bool:
        return tx in self


@lru_cache_lite
def _get_getter(attribute: str) -> attrgetter:
    return attrgetter(attribute)


class Filter:
    def __init__(self, attribute: str, value: Any = None) -> None:
        self.get_attribute = _get_getter(attribute)
        self.value = value

    def __contains__(self, tx: TreasuryTx) -> bool:
        return self.get_attribute(tx) == self.value


class IterFilter(Filter):
    def __init__(self, attribute: str, values: Iterable) -> None:
        self.values = set(values)
        Filter.__init__(self, attribute)
    
    def __contains__(self, tx: TreasuryTx) -> bool:
        return self.get_attribute(tx) in self.values


_FROM_DISPERSE_APP = Filter('_from_nickname', 'Disperse.app')