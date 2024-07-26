import { Module } from '@nestjs/common';
import { DirigeraModule } from './dirigera/dirigera.module';

@Module({
  imports: [DirigeraModule],
  exports: [DirigeraModule],
})
export class ConsumersModule {}
