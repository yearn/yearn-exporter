
import logging
from requests import HTTPError
from typing import Any, Callable, Iterable, List, Optional, Tuple, Union

import sentry_sdk
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
                print(f'sorted {tx} to {self.label}')
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
            if not isinstance(result, bool):
                raise TypeError(result, self, self.check)
            if result:
                print(f"sorted {tx} to {self.label}")
                return self.txgroup
        except ContractNotVerified:
            logger.info("ContractNotVerified when sorting %s with %s", tx, self.label)
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
    def __init__(self, hashes: Iterable[Union[str,Tuple[str,"Filter"]]]) -> None:
        self.hashes = [hash.lower() if isinstance(hash,str) else hash for hash in hashes]
    
    def __contains__(self, tx: TreasuryTx) -> bool:
        hash = tx.hash.lower()
        for matcher in self.hashes:
            if isinstance(matcher, str):
                if hash == matcher:
                    return True
            else:
                matcher, filter = matcher
                if hash == matcher and tx in filter:
                    return True
        return False
    
    def contains(self, tx: TreasuryTx) -> bool:
        return tx in self


class Filter:
    def __init__(self, attribute: str, value: Any = None) -> None:
        self.attributes = attribute.split('.') if '.' in attribute else [attribute]
        self.value = value

    def __contains__(self, object: Any) -> bool:
        return self.get_attribute(object) == self.value
    
    def get_attribute(self, object: Any) -> Any:
        for attr in self.attributes:
            object = getattr(object, attr)
        return object


class IterFilter(Filter):
    def __init__(self, attribute: str, values: Iterable) -> None:
        self.values = values
        super().__init__(attribute)
    
    def __contains__(self, tx: Any) -> bool:
        return self.get_attribute(tx) in self.values
