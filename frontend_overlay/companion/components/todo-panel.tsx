import { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Checkbox,
  HStack,
  IconButton,
  Input,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FiPlus, FiTrash2, FiRefreshCw } from 'react-icons/fi';
import { useCompanionApi, type Todo } from '@/hooks/use-companion-api';

const statusFilters: Array<'pending' | 'completed' | 'all'> = [
  'pending',
  'completed',
  'all',
];

function formatDue(due: number | null): string {
  if (!due) return '';
  try {
    return new Date(due * 1000).toLocaleString();
  } catch {
    return '';
  }
}

function TodoPanel(): JSX.Element {
  const api = useCompanionApi();
  const [items, setItems] = useState<Todo[]>([]);
  const [filter, setFilter] = useState<'pending' | 'completed' | 'all'>('pending');
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const todos = await api.listTodos(filter);
      setItems(todos);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [api, filter]);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 8000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const onSubmit = useCallback(async () => {
    const title = draft.trim();
    if (!title) return;
    try {
      await api.createTodo({ title });
      setDraft('');
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }, [api, draft, refresh]);

  const toggleStatus = useCallback(
    async (todo: Todo) => {
      try {
        await api.updateTodo(todo.id, {
          status: todo.status === 'pending' ? 'completed' : 'pending',
        });
        await refresh();
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [api, refresh],
  );

  const remove = useCallback(
    async (todo: Todo) => {
      try {
        await api.deleteTodo(todo.id);
        await refresh();
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [api, refresh],
  );

  return (
    <Box p={3} bg="whiteAlpha.50" borderRadius="md">
      <HStack mb={3} justify="space-between">
        <Text fontWeight="bold">To-do</Text>
        <HStack gap={1}>
          {statusFilters.map((s) => (
            <Button
              key={s}
              size="xs"
              variant={filter === s ? 'solid' : 'ghost'}
              onClick={() => setFilter(s)}
            >
              {s}
            </Button>
          ))}
          <IconButton size="xs" aria-label="refresh" onClick={refresh} loading={busy}>
            <FiRefreshCw />
          </IconButton>
        </HStack>
      </HStack>

      <HStack mb={3}>
        <Input
          size="sm"
          placeholder="Add a task..."
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onSubmit();
          }}
        />
        <IconButton size="sm" aria-label="add" onClick={onSubmit}>
          <FiPlus />
        </IconButton>
      </HStack>

      {error && (
        <Text color="red.300" fontSize="xs" mb={2}>
          {error}
        </Text>
      )}

      <VStack align="stretch" gap={1.5} maxH="300px" overflowY="auto">
        {items.length === 0 && (
          <Text color="whiteAlpha.500" fontSize="sm">
            No items.
          </Text>
        )}
        {items.map((todo) => (
          <HStack
            key={todo.id}
            justify="space-between"
            p={2}
            borderRadius="md"
            bg="whiteAlpha.100"
          >
            <HStack flex={1} minW={0}>
              <Checkbox.Root
                checked={todo.status === 'completed'}
                onCheckedChange={() => toggleStatus(todo)}
              >
                <Checkbox.HiddenInput />
                <Checkbox.Control />
              </Checkbox.Root>
              <Box minW={0}>
                <Text
                  fontSize="sm"
                  textDecoration={
                    todo.status === 'completed' ? 'line-through' : 'none'
                  }
                  truncate
                >
                  {todo.title}
                </Text>
                {todo.due_at && (
                  <Text fontSize="xs" color="whiteAlpha.600">
                    due {formatDue(todo.due_at)}
                  </Text>
                )}
              </Box>
            </HStack>
            <IconButton
              size="xs"
              variant="ghost"
              aria-label="delete"
              onClick={() => remove(todo)}
            >
              <FiTrash2 />
            </IconButton>
          </HStack>
        ))}
      </VStack>
    </Box>
  );
}

export default TodoPanel;
