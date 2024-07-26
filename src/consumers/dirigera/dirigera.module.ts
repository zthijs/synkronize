import { Module } from '@nestjs/common';
import { DirigeraController } from './dirigera.controller';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Consumer } from '../consumer.entity';
import { DirigeraService } from './dirigera.service';
import { Provider } from '@/providers/provider.entity';

@Module({
  imports: [TypeOrmModule.forFeature([Consumer, Provider])],
  controllers: [DirigeraController],
  providers: [DirigeraService],
  exports: [DirigeraService],
})
export class DirigeraModule {}
