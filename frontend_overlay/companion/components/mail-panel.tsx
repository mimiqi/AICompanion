import { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  HStack,
  IconButton,
  Spinner,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FiRefreshCw, FiArrowLeft } from 'react-icons/fi';
import { useCompanionApi, type MailDetail, type MailSummary } from '@/hooks/use-companion-api';

function formatDate(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function MailPanel(): JSX.Element {
  const api = useCompanionApi();
  const [list, setList] = useState<MailSummary[]>([]);
  const [unreadOnly, setUnreadOnly] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<MailDetail | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const emails = await api.listRecentMail(unreadOnly, 30);
      setList(emails);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [api, unreadOnly]);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 30000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const open = useCallback(
    async (uid: string) => {
      setBusy(true);
      setError(null);
      try {
        const detail = await api.getMailDetail(uid);
        setActive(detail);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [api],
  );

  if (active) {
    return (
      <Box p={3} bg="whiteAlpha.50" borderRadius="md">
        <HStack mb={2}>
          <IconButton size="xs" aria-label="back" onClick={() => setActive(null)}>
            <FiArrowLeft />
          </IconButton>
          <Text fontWeight="bold" truncate>
            {active.subject || '(no subject)'}
          </Text>
        </HStack>
        <Text fontSize="xs" color="whiteAlpha.700" mb={2}>
          {active.sender}  -  {formatDate(active.date)}
        </Text>
        <Box
          fontSize="sm"
          maxH="320px"
          overflowY="auto"
          whiteSpace="pre-wrap"
          color="whiteAlpha.900"
        >
          {active.body || '(empty body)'}
        </Box>
      </Box>
    );
  }

  return (
    <Box p={3} bg="whiteAlpha.50" borderRadius="md">
      <HStack mb={3} justify="space-between">
        <Text fontWeight="bold">Inbox</Text>
        <HStack gap={1}>
          <Button
            size="xs"
            variant={unreadOnly ? 'solid' : 'ghost'}
            onClick={() => setUnreadOnly(true)}
          >
            unread
          </Button>
          <Button
            size="xs"
            variant={!unreadOnly ? 'solid' : 'ghost'}
            onClick={() => setUnreadOnly(false)}
          >
            all
          </Button>
          <IconButton size="xs" aria-label="refresh" onClick={refresh} loading={busy}>
            <FiRefreshCw />
          </IconButton>
        </HStack>
      </HStack>

      {error && (
        <Text color="red.300" fontSize="xs" mb={2}>
          {error}
        </Text>
      )}

      {busy && list.length === 0 && <Spinner size="sm" />}

      <VStack align="stretch" gap={1.5} maxH="300px" overflowY="auto">
        {list.length === 0 && !busy && (
          <Text color="whiteAlpha.500" fontSize="sm">
            No emails.
          </Text>
        )}
        {list.map((m) => (
          <Box
            key={m.uid}
            p={2}
            borderRadius="md"
            bg={m.is_unread ? 'blue.900/40' : 'whiteAlpha.100'}
            cursor="pointer"
            onClick={() => open(m.uid)}
            _hover={{ bg: 'whiteAlpha.200' }}
          >
            <Text fontSize="sm" fontWeight={m.is_unread ? 'bold' : 'normal'} truncate>
              {m.subject || '(no subject)'}
            </Text>
            <Text fontSize="xs" color="whiteAlpha.700" truncate>
              {m.sender}
            </Text>
            <Text fontSize="xs" color="whiteAlpha.500">
              {formatDate(m.date)}
            </Text>
          </Box>
        ))}
      </VStack>
    </Box>
  );
}

export default MailPanel;
